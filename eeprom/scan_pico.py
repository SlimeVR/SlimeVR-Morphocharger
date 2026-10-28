import time
from machine import I2C, Pin

EEPROM_ADDR = 0x50
EEPROM_SIZE = 256
RESET_SETTLE_MS = 50

SDA_PIN = 4
SCL_PIN = 5
WP_PIN = 6


def level(value):
	return "HIGH" if value else "LOW "


def read_lines():
	for pull, name in ((Pin.PULL_UP, "pull-up  "), (Pin.PULL_DOWN, "pull-down")):
		sda = Pin(SDA_PIN, Pin.IN, pull)
		scl = Pin(SCL_PIN, Pin.IN, pull)
		time.sleep_ms(5)
		print("    %s  SCL %s  SDA %s" % (name, level(scl.value()), level(sda.value())))


def print_map(found):
	print("        " + " ".join(" %X" % c for c in range(16)))
	for row in range(0, 0x80, 0x10):
		cells = ["%02X" % a if a in found else "--" for a in range(row, row + 0x10)]
		print("    %02X: %s" % (row, " ".join(cells)))


def print_eeprom(data):
	print("    EEPROM contents:")
	for row in range(0, EEPROM_SIZE, 16):
		chunk = data[row : row + 16]
		hexed = " ".join("%02X" % b for b in chunk)
		text = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in chunk)
		print("    %02X: %s  %s" % (row, hexed, text))

	print_fields(data)


def bit(value, n):
	return (value >> n) & 1


def unicode_string(data, len_plus_2_at, len_at, max_bytes):
	length = data[len_at]
	if length > max_bytes:
		return "<invalid length %d>" % length
	start = len_at + 1
	text = "".join(chr(data[i] | data[i + 1] << 8) for i in range(start, start + length - 1, 2))
	return "%r  (len %d, len+2 %d)" % (text, length, data[len_plus_2_at])


def print_fields(data):
	# Layout from CH334/335 datasheet V2.5, tables 3-5-1 and 3-5-2
	vid = data[0x00] | data[0x01] << 8
	pid = data[0x02] | data[0x03] << 8
	expected_checksum = (data[0x00] + data[0x01] + data[0x02] + data[0x03] + 1) & 0xFF
	removable = data[0x06]
	cfg = data[0x0A]

	print("    decoded:")
	print("      00-03 VID:PID         %04X:%04X" % (vid, pid))
	if data[0x04] == expected_checksum:
		checksum_state = "ok"
	else:
		checksum_state = "BAD, expected 0x%02X, hub ignores the EEPROM" % expected_checksum
	print("      04    checksum        0x%02X  %s" % (data[0x04], checksum_state))
	for port in range(1, 5):
		print("      06    port %d          %s" % (port, "non-removable" if bit(removable, port) else "removable"))
	print("      07    port number     %d  %s" % (data[0x07], "ok" if 1 <= data[0x07] <= 4 else "INVALID, must be 1-4"))
	print("      08    max power       %d mA  (0x%02X)" % (data[0x08] * 2, data[0x08]))
	signature_state = "ok" if data[0x09] == 0x5A else "BAD, must be 0x5A, config byte ignored"
	print("      09    signature       0x%02X  %s" % (data[0x09], signature_state))
	print("      0A    config          0x%02X" % cfg)
	print("            bit 6 USB rewrite   %s" % ("allowed" if bit(cfg, 6) else "write protected"))
	print("            bit 5 OC level      %s" % ("4.1V, weak pull-down" if bit(cfg, 5) else "2.4V, weak pull-up"))
	print("            bit 4 reserved      %d  %s" % (bit(cfg, 4), "ok" if bit(cfg, 4) else "BAD, must be 1"))
	print("            bit 3 reserved      %d  %s" % (bit(cfg, 3), "ok" if not bit(cfg, 3) else "BAD, must be 0"))
	print("            bit 2 power         %s" % ("self-powered" if bit(cfg, 2) else "bus-powered"))
	print("            bit 1 indicator     %s" % ("LEDs on" if bit(cfg, 1) else "LEDs off"))
	print("            bit 0 overcurrent   %s" % ("gang" if bit(cfg, 0) else "independent"))
	print("      3F-6E product         %s" % unicode_string(data, 0x3F, 0x40, 46))
	print("      6F-9F serial          %s" % unicode_string(data, 0x6F, 0x70, 47))


def scan():
	print("WP/RESET# released (hub running), WP reads %d" % Pin(WP_PIN, Pin.IN).value())
	read_lines()

	Pin(WP_PIN, Pin.OUT, value=0)
	time.sleep_ms(RESET_SETTLE_MS)
	print("WP/RESET# low (hub in reset)")
	read_lines()

	i2c = I2C(0, sda=Pin(SDA_PIN, pull=Pin.PULL_UP), scl=Pin(SCL_PIN, pull=Pin.PULL_UP), freq=100_000)
	try:
		found = i2c.scan()
	except OSError as e:
		print("    scan failed: %r" % e)
		return
	print_map(found)
	if EEPROM_ADDR not in found:
		print("    EEPROM: not found")
		return
	print("    EEPROM: found at 0x50")
	print_eeprom(i2c.readfrom_mem(EEPROM_ADDR, 0, EEPROM_SIZE))


try:
	scan()
finally:
	Pin(WP_PIN, Pin.IN)
