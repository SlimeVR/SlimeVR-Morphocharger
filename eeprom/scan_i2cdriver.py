import argparse
import time

import i2cdriver
from serial.tools import list_ports

EEPROM_ADDR = 0x50
EEPROM_SIZE = 256
READ_CHUNK = 128  # regrd sends the length as one byte, so 256 would read 0

# 4.7k on SDA and SCL, the I2CDriver boot default
PULLUPS = 0b100_100
SETTLE_S = 0.01


def level(value):
	return "HIGH" if value else "LOW "


def print_map(found):
	print("        " + " ".join(f" {c:X}" for c in range(16)))
	for row in range(0, 0x80, 0x10):
		cells = [f"{a:02X}" if a in found else "--" for a in range(row, row + 0x10)]
		print(f"    {row:02X}: " + " ".join(cells))


def print_eeprom(i2c):
	data = b"".join(i2c.regrd(EEPROM_ADDR, offset, READ_CHUNK) for offset in range(0, EEPROM_SIZE, READ_CHUNK))

	print("    EEPROM contents:")
	for row in range(0, EEPROM_SIZE, 16):
		chunk = data[row : row + 16]
		hexed = " ".join(f"{b:02X}" for b in chunk)
		text = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in chunk)
		print(f"    {row:02X}: {hexed}  {text}")

	print_fields(data)


def unicode_string(data, len_plus_2_at, len_at, max_bytes):
	length = data[len_at]
	if length > max_bytes:
		return f"<invalid length {length}>"
	text = data[len_at + 1 : len_at + 1 + length].decode("utf-16-le", "replace")
	return f"{text!r}  (len {length}, len+2 {data[len_plus_2_at]})"


def print_fields(data):
	vid = int.from_bytes(data[0x00:0x02], "little")
	pid = int.from_bytes(data[0x02:0x04], "little")
	expected_checksum = (sum(data[0x00:0x04]) + 1) & 0xFF
	removable = data[0x06]
	cfg = data[0x0A]
	cfg_valid = data[0x09] == 0x5A

	def bit(value, n):
		return (value >> n) & 1

	print("    decoded:")
	print(f"      00-03 VID:PID         {vid:04X}:{pid:04X}")
	checksum_state = "ok" if data[0x04] == expected_checksum else f"BAD, expected 0x{expected_checksum:02X}, hub ignores the EEPROM"
	print(f"      04    checksum        0x{data[0x04]:02X}  {checksum_state}")
	for port in range(1, 5):
		state = "non-removable" if bit(removable, port) else "removable"
		print(f"      06    port {port}          {state}")
	print(f"      07    port number     {data[0x07]}  {'ok' if 1 <= data[0x07] <= 4 else 'INVALID, must be 1-4'}")
	print(f"      08    max power       {data[0x08] * 2} mA  (0x{data[0x08]:02X})")
	print(f"      09    signature       0x{data[0x09]:02X}  {'ok' if cfg_valid else 'BAD, must be 0x5A, config byte ignored'}")
	print(f"      0A    config          0x{cfg:02X}")
	print(f"            bit 6 USB rewrite   {'allowed' if bit(cfg, 6) else 'write protected'}")
	print(f"            bit 5 OC level      {'4.1V, weak pull-down' if bit(cfg, 5) else '2.4V, weak pull-up'}")
	print(f"            bit 4 reserved      {bit(cfg, 4)}  {'ok' if bit(cfg, 4) else 'BAD, must be 1'}")
	print(f"            bit 3 reserved      {bit(cfg, 3)}  {'ok' if not bit(cfg, 3) else 'BAD, must be 0'}")
	print(f"            bit 2 power         {'self-powered' if bit(cfg, 2) else 'bus-powered'}")
	print(f"            bit 1 indicator     {'LEDs on' if bit(cfg, 1) else 'LEDs off'}")
	print(f"            bit 0 overcurrent   {'gang' if bit(cfg, 0) else 'independent'}")
	print(f"      3F-6E product         {unicode_string(data, 0x3F, 0x40, 46)}")
	print(f"      6F-9F serial          {unicode_string(data, 0x6F, 0x70, 47)}")


def scan(i2c):
	i2c.setpullups(PULLUPS)
	time.sleep(SETTLE_S)
	i2c.getstatus()

	print(f"    SCL {level(i2c.scl)}   SDA {level(i2c.sda)}   supply {i2c.voltage:.2f} V   current {i2c.current:.0f} mA")

	if (i2c.scl, i2c.sda) != (1, 1):
		print("    bus held low, not scanning")
		return

	found = i2c.scan(silent=True)
	print_map(found)
	if EEPROM_ADDR not in found:
		print("    EEPROM: not found")
		return

	print("    EEPROM: found at 0x50")
	print_eeprom(i2c)


# The I2CDriver is built on an FTDI FT230X
I2CDRIVER_USB_ID = (0x0403, 0x6015)


def find_i2cdriver_port():
	for port in list_ports.comports():
		if (port.vid, port.pid) == I2CDRIVER_USB_ID:
			return port.device
	return None


def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--port", help="I2CDriver serial port, found by USB ID when omitted")
	args = parser.parse_args()

	port = args.port or find_i2cdriver_port()
	if port is None:
		print("no I2CDriver found, pass --port")
		return

	i2c = i2cdriver.I2CDriver(port, reset="never")
	i2c.setspeed(100)

	scan(i2c)


if __name__ == "__main__":
	main()
