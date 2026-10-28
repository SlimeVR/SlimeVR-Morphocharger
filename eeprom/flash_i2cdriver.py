import argparse
import time

import i2cdriver
from serial.tools import list_ports

from eeprom_image import EEPROM_SIZE, build_image

EEPROM_ADDR = 0x50
PAGE_SIZE = 8  # smallest 24C02 page size, safe on every vendor
READ_CHUNK = 128
WRITE_TIMEOUT_MS = 50

# 4.7k on SDA and SCL
PULLUPS = 0b100_100


def address_acked(i2c):
	acked = i2c.start(EEPROM_ADDR, 0)
	i2c.stop()
	return acked


def write_page(i2c, offset, data):
	return i2c.regwr(EEPROM_ADDR, offset, data)


def wait_write_done(i2c):
	# The EEPROM NAKs its address until the internal write cycle ends
	deadline = time.monotonic() + WRITE_TIMEOUT_MS / 1000
	while time.monotonic() < deadline:
		if address_acked(i2c):
			return True
	return False


# The I2CDriver is built on an FTDI FT230X
I2CDRIVER_USB_ID = (0x0403, 0x6015)


def find_i2cdriver_port():
	for port in list_ports.comports():
		if (port.vid, port.pid) == I2CDRIVER_USB_ID:
			return port.device
	return None


def main():
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument("--port", help="I2CDriver serial port, found by USB ID when omitted")
	parser.add_argument("--serial", help="USB serial number string, left empty when omitted")
	args = parser.parse_args()

	try:
		image = build_image(args.serial)
	except ValueError as e:
		print(e)
		return

	port = args.port or find_i2cdriver_port()
	if port is None:
		print("no I2CDriver found, pass --port")
		return

	i2c = i2cdriver.I2CDriver(port, reset="never")
	i2c.setspeed(100)
	i2c.setpullups(PULLUPS)
	i2c.getstatus()
	if (i2c.scl, i2c.sda) != (1, 1):
		print(f"bus is not idle (SCL={i2c.scl} SDA={i2c.sda}), something on the board holds a line low")
		return
	if EEPROM_ADDR not in i2c.scan(silent=True):
		print("EEPROM not found at 0x50, check contact and power")
		return

	for offset in range(0, EEPROM_SIZE, PAGE_SIZE):
		if not write_page(i2c, offset, image[offset : offset + PAGE_SIZE]):
			print("write NAKed at 0x%02X" % offset)
			return
		if not wait_write_done(i2c):
			print("EEPROM did not finish writing 0x%02X" % offset)
			return

	readback = b"".join(i2c.regrd(EEPROM_ADDR, offset, READ_CHUNK) for offset in range(0, EEPROM_SIZE, READ_CHUNK))
	bad = [i for i in range(EEPROM_SIZE) if readback[i] != image[i]]
	if bad:
		print(f"verify failed at {len(bad)} bytes, first at 0x{bad[0]:02X} (WP not held low leaves the old content)")
		return

	print("OK")


if __name__ == "__main__":
	main()
