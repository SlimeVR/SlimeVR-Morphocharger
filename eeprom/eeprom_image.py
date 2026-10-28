EEPROM_SIZE = 256

VID = 0x1209
PID = 0x7694
PRODUCT = "SlimeVR Morpho Charger"

# Bit 1 = downstream port 1. P2-P4 feed the onboard CH334P hubs, P1 is the USB-A port
DEVICE_REMOVABLE = 0b0001_1100
PORT_NUMBER = 4
MAX_POWER_MA = 100

CFG_WRITE_ALLOWED = 0 << 6  # no rewrite from a USB tool
CFG_OC_LEVEL = 0 << 5  # 2.4V + weak pull-up, OVCUR# is unconnected
CFG_RESERVED = 1 << 4  # bit 4 must be 1, bit 3 must be 0
CFG_SELF_POWER = 0 << 2  # bus-powered, matches PSELF tied to GND
CFG_INDICATOR_EN = 0 << 1  # LED1/LED2 are unconnected
CFG_GANG_MODE = 1 << 0  # only mode the CH334F supports

# Product string runs 41h-6Eh, serial 71h-9Fh
PRODUCT_MAX_BYTES = 46
SERIAL_MAX_BYTES = 46


def utf16le(text):
	out = bytearray()
	for c in text:
		code = ord(c)
		if code > 0xFFFF:
			raise ValueError("%r is outside the basic multilingual plane" % c)
		out.append(code & 0xFF)
		out.append(code >> 8)
	return bytes(out)


def write_string(image, len_plus_2_at, text, max_bytes, name):
	encoded = utf16le(text)
	if len(encoded) > max_bytes:
		raise ValueError("%s is %d characters, max %d" % (name, len(text), max_bytes // 2))
	image[len_plus_2_at] = len(encoded) + 2
	image[len_plus_2_at + 1] = len(encoded)
	start = len_plus_2_at + 2
	image[start : start + len(encoded)] = encoded


def build_image(serial=None):
	"""Returns the 256 byte image. Without a serial the serial string is left empty."""
	image = bytearray(b"\xff" * EEPROM_SIZE)

	image[0x00] = VID & 0xFF
	image[0x01] = VID >> 8
	image[0x02] = PID & 0xFF
	image[0x03] = PID >> 8
	image[0x04] = (image[0x00] + image[0x01] + image[0x02] + image[0x03] + 1) & 0xFF
	image[0x06] = DEVICE_REMOVABLE
	image[0x07] = PORT_NUMBER
	image[0x08] = MAX_POWER_MA // 2
	image[0x09] = 0x5A
	image[0x0A] = (
		CFG_WRITE_ALLOWED | CFG_OC_LEVEL | CFG_RESERVED | CFG_SELF_POWER | CFG_INDICATOR_EN | CFG_GANG_MODE
	)

	write_string(image, 0x3F, PRODUCT, PRODUCT_MAX_BYTES, "product")

	if serial:
		write_string(image, 0x6F, serial, SERIAL_MAX_BYTES, "serial")
	else:
		image[0x6F] = 0x00
		image[0x70] = 0x00

	return bytes(image)
