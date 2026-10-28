# MicroPython for a Raspberry Pi Pico. Writes the hub image to the dock EEPROM and reads it back.
# mount makes eeprom_image.py importable on the Pico without copying it:
#   mpremote mount . run eeprom/flash_pico.py
#
# Wiring (pogo pins, Pico GND to dock GND):
#   GP4 -> TP3 SDA
#   GP5 -> TP4 SCL
#   GP6 -> TP2 WP, also wired to the hub RESET#. Low unlocks the EEPROM and holds the hub in reset
#          so it lets go of the bus. Released at the end, R3 pulls it back up and the hub boots on the new image
import time
from machine import I2C, Pin

from eeprom_image import EEPROM_SIZE, build_image

EEPROM_ADDR = 0x50
PAGE_SIZE = 8  # smallest 24C02 page size, safe on every vendor
WRITE_TIMEOUT_MS = 50
RESET_SETTLE_MS = 50

SDA_PIN = 4
SCL_PIN = 5
WP_PIN = 6


def bus_idle():
	sda = Pin(SDA_PIN, Pin.IN, Pin.PULL_UP)
	scl = Pin(SCL_PIN, Pin.IN, Pin.PULL_UP)
	time.sleep_ms(5)
	print("SCL %s  SDA %s" % ("HIGH" if scl.value() else "LOW", "HIGH" if sda.value() else "LOW"))
	return scl.value() == 1 and sda.value() == 1


def address_acked(i2c):
	try:
		i2c.writeto(EEPROM_ADDR, b"")
		return True
	except OSError:
		return False


def write_page(i2c, offset, data):
	try:
		i2c.writeto_mem(EEPROM_ADDR, offset, data)
		return True
	except OSError:
		return False


def wait_write_done(i2c):
	# The EEPROM NAKs its address until the internal write cycle ends
	deadline = time.ticks_add(time.ticks_ms(), WRITE_TIMEOUT_MS)
	while time.ticks_diff(deadline, time.ticks_ms()) > 0:
		if address_acked(i2c):
			return True
	return False


def flash(image):
	if not bus_idle():
		print("bus held low with WP/RESET# low, the hub is not letting go of SCL/SDA")
		return

	i2c = I2C(0, sda=Pin(SDA_PIN, pull=Pin.PULL_UP), scl=Pin(SCL_PIN, pull=Pin.PULL_UP), freq=100_000)
	if EEPROM_ADDR not in i2c.scan():
		print("EEPROM not found at 0x50, check pogo contact and dock power")
		return

	for offset in range(0, EEPROM_SIZE, PAGE_SIZE):
		if not write_page(i2c, offset, image[offset : offset + PAGE_SIZE]):
			print("write NAKed at 0x%02X" % offset)
			return
		if not wait_write_done(i2c):
			print("EEPROM did not finish writing 0x%02X" % offset)
			return

	readback = i2c.readfrom_mem(EEPROM_ADDR, 0, EEPROM_SIZE)
	if readback != image:
		bad = [i for i in range(EEPROM_SIZE) if readback[i] != image[i]]
		print("verify failed at %d bytes, first at 0x%02X (WP not low leaves the old content)" % (len(bad), bad[0]))
		return

	print("OK")


def main(serial=None):
	try:
		image = build_image(serial)
	except ValueError as e:
		print(e)
		return

	Pin(WP_PIN, Pin.OUT, value=0)
	time.sleep_ms(RESET_SETTLE_MS)
	try:
		flash(image)
	finally:
		Pin(WP_PIN, Pin.IN)


if __name__ == "__main__":
	main()
