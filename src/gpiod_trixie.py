"""
src/gpiod_trixie.py

Trixie-only shim that emulates the classic libgpiod v1 Python API
(Chip, get_line, Line.request, etc.) on top of libgpiod.so.2 via ctypes.

Use this ONLY on Trixie:

    import compat_gpiod_trixie as gpiod

    chip = gpiod.Chip("gpiochip0")
    line = chip.get_line(17)
    line.request_input("myapp")
    v = line.get_value()
"""

import ctypes
import ctypes.util

# ---------------------------------------------------------------------------
# Load libgpiod2
# ---------------------------------------------------------------------------

_lib = ctypes.CDLL(ctypes.util.find_library("gpiod"))

# ---------------------------------------------------------------------------
# v1-style constants
# ---------------------------------------------------------------------------

LINE_REQ_DIR_IN  = 1
LINE_REQ_DIR_OUT = 2

LINE_REQ_FLAG_ACTIVE_LOW   = 0x01
LINE_REQ_FLAG_OPEN_DRAIN   = 0x02
LINE_REQ_FLAG_OPEN_SOURCE  = 0x04

LINE_REQ_FLAG_BIAS_DISABLE   = 0x100
LINE_REQ_FLAG_BIAS_PULL_UP   = 0x200
LINE_REQ_FLAG_BIAS_PULL_DOWN = 0x400

# ---------------------------------------------------------------------------
# ctypes structures and function signatures (v1 ABI inside libgpiod2)
# ---------------------------------------------------------------------------

class _gpiod_chip(ctypes.Structure):
    pass

class _gpiod_line(ctypes.Structure):
    pass

_lib.gpiod_chip_open.restype = ctypes.POINTER(_gpiod_chip)
_lib.gpiod_chip_open.argtypes = [ctypes.c_char_p]

_lib.gpiod_chip_close.restype = None
_lib.gpiod_chip_close.argtypes = [ctypes.POINTER(_gpiod_chip)]

_lib.gpiod_chip_get_line.restype = ctypes.POINTER(_gpiod_line)
_lib.gpiod_chip_get_line.argtypes = [ctypes.POINTER(_gpiod_chip),
                                     ctypes.c_uint]

_lib.gpiod_line_request.restype = ctypes.c_int
_lib.gpiod_line_request.argtypes = [
    ctypes.POINTER(_gpiod_line),
    ctypes.c_char_p,
    ctypes.c_int,
    ctypes.POINTER(ctypes.c_int),
    ctypes.c_int,
]

_lib.gpiod_line_set_value.restype = ctypes.c_int
_lib.gpiod_line_set_value.argtypes = [ctypes.POINTER(_gpiod_line),
                                      ctypes.c_int]

_lib.gpiod_line_get_value.restype = ctypes.c_int
_lib.gpiod_line_get_value.argtypes = [ctypes.POINTER(_gpiod_line)]

if hasattr(_lib, "gpiod_line_release"):
    _lib.gpiod_line_release.restype = None
    _lib.gpiod_line_release.argtypes = [ctypes.POINTER(_gpiod_line)]
else:
    _lib.gpiod_line_release = None

# ---------------------------------------------------------------------------
# Public API: Line and Chip (v1-style)
# ---------------------------------------------------------------------------

class Line:
    def __init__(self, chip, offset):
        self._chip = chip._chip
        self._line = _lib.gpiod_chip_get_line(self._chip, offset)

    def request(self, consumer, type, default_vals=None, flags=0):
        default_val = 0
        if default_vals:
            default_val = default_vals[0]

        val = ctypes.c_int(default_val)

        _lib.gpiod_line_request(
            self._line,
            consumer.encode(),
            type | flags,
            ctypes.byref(val),
            0,
        )

    def request_output(self, consumer, default_val=0, flags=0):
        self.request(consumer, LINE_REQ_DIR_OUT, [default_val], flags)

    def request_input(self, consumer, flags=0):
        self.request(consumer, LINE_REQ_DIR_IN, None, flags)

    def set_value(self, value):
        _lib.gpiod_line_set_value(self._line, int(value))

    def get_value(self):
        return _lib.gpiod_line_get_value(self._line)

    def release(self):
        if _lib.gpiod_line_release is not None:
            _lib.gpiod_line_release(self._line)


class Chip:
    def __init__(self, name):
        path = name if name.startswith("/dev/") else f"/dev/{name}"
        self._chip = _lib.gpiod_chip_open(path.encode())

    def get_line(self, offset):
        return Line(self, offset)

    def close(self):
        _lib.gpiod_chip_close(self._chip)
