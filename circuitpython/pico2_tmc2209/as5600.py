# SPDX-FileCopyrightText: Copyright (c) 2025 Noel Anderson
#
# SPDX-License-Identifier: MIT
"""
`as5600`
================================================================================

CircuitPython helper library for the AMS AS5600 12-bit on-axis magnetic rotary position sensor


* Author(s): Noel Anderson

Implementation Notes
--------------------

**Hardware:**

* AS5600 <https://ams.com/as5600>

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads

* Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice
"""

# imports

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/noelanderson/CircuitPython_AS5600.git"


from adafruit_bus_device import i2c_device
from micropython import const

try:
    from typing import NoReturn
except ImportError:
    pass

# Register Map & bit positions

_AS5600_DEFAULT_I2C_ADDR = const(0x36)
_REG_ZMCO = const(0x00)  # R
_REG_ZPOS_HI = const(0x01)  # R/W/P
_REG_ZPOS_LO = const(0x02)  # R/W/P
_REG_MPOS_HI = const(0x03)  # R/W/P
_REG_MPOS_LO = const(0x04)  # R/W/P
_REG_MANG_HI = const(0x05)  # R/W/P
_REG_MANG_LO = const(0x06)  # R/W/P

# ---------------------------------------------------------------#
#    7   |   6   |   5   |   4   |   3   |   2   |   1   |   0   |
# -------+-------+-------+-------+-------+-------+-------+-------|
#        |       |   WD  |          FTH          |       SF      |
# ---------------------------------------------------------------#
_REG_CONF_HI = const(0x07)  # R/W/P
_BIT_POS_SF = const(0)
_BIT_POS_FTH = const(2)
_BIT_POS_WD = const(5)

# ---------------------------------------------------------------#
#    7   |   6   |   5   |   4   |   3   |   2   |   1   |   0   |
# -------+-------+-------+-------+-------+-------+-------+-------|
#       PWMF     |     OUTS      |     HYST      |      PM       |
# ---------------------------------------------------------------#
_REG_CONF_LO = const(0x08)  # R/W/P
_BIT_POS_PM = const(0)
_BIT_POS_HYST = const(2)
_BIT_POS_OUTS = const(4)
_BIT_POS_PWMF = const(6)

_REG_RAW_ANGLE_HI = const(0x0C)  # R
_REG_RAW_ANGLE_LO = const(0x0D)  # R
_REG_ANGLE_HI = const(0x0E)  # R
_REG_ANGLE_LO = const(0x0F)  # R

# ---------------------------------------------------------------#
#    7   |   6   |   5   |   4   |   3   |   2   |   1   |   0   |
# -------+-------+-------+-------+-------+-------+-------+-------|
#        |       |   MD  |   ML  |   MH  |       |       |       |
# ---------------------------------------------------------------#
_REG_STATUS = const(0x0B)  # R
_STATUS_MH = const(0b00001000)
_STATUS_ML = const(0b00010000)
_STATUS_MD = const(0b00100000)

_REG_AGC = const(0x1A)  # R
_REG_MAGNITUDE_HI = const(0x1B)  # R
_REG_MAGNITUDE_LO = const(0x1C)  # R
_REG_BURN = const(0xFF)  # W

# Commands

_BURN_ANGLE_COMMAND = const(0x80)
_BURN_SETTINGS_COMMAND = const(0x40)

_1_BIT = const(0b00000001)
_2_BITS = const(0b00000011)
_3_BITS = const(0b00000111)


class AS5600:  # noqa PLR0904
    """
    Initialize the AS5600 chip at ``address`` on ``i2c_bus``.

    :param i2c: The I2C bus object.
    :type i2c: I2C
    :param address: The I2C address of the device. Default is 0x36.
    :type address: int
    """

    # User-facing constants:
    POWER_MODE_NOM = const(0)
    """ Always on (PM) mode - 6.5mA"""
    POWER_MODE_LPM1 = const(1)
    """ Low Power (LPM1) mode - 3.4mA, Polling Time = 5mS"""
    POWER_MODE_LPM2 = const(2)
    """ Low Power (LPM2) mode - 1.8mA, Polling Time = 20mS"""
    POWER_MODE_LPM3 = const(3)
    """ Low Power (LPM3) mode - 1.5mA, Polling Time = 100mS"""

    HYSTERESIS_OFF = const(0)
    """ Hysteresis (HYST) off"""
    HYSTERESIS_1LSB = const(1)
    """ Hysteresis (HYST) 1 LSB"""
    HYSTERESIS_2LSB = const(2)
    """ Hysteresis (HYST) 2 LSB"""
    HYSTERESIS_3LSB = const(3)
    """ Hysteresis (HYST) 3 LSB"""

    OUTPUT_STAGE_ANALOG_FULL = const(0)
    """ Output Stage (OUTS) full range analog output 0-100% GND to VDD"""
    OUTPUT_STAGE_ANALOG_REDUCED = const(1)
    """ Output Stage (OUTS) reduced range analog output 10-90% GND to VDD"""
    OUTPUT_STAGE_DIGITAL_PWM = const(2)
    """ Output Stage (OUTS) digital PWM output"""

    PWM_FREQUENCY_115HZ = const(0)
    """  PWM Frequency (PWMF) 115Hz"""
    PWM_FREQUENCY_230HZ = const(1)
    """ PWM Frequency (PWMF) 230Hz"""
    PWM_FREQUENCY_460HZ = const(2)
    """PWM Frequency (PWMF) 460Hz"""
    PWM_FREQUENCY_920HZ = const(3)
    """ PWM Frequency (PWMF) 920Hz"""

    SLOW_FILTER_16X = const(0)
    """ Slow Filter (SF) 16x"""
    SLOW_FILTER_8X = const(1)
    """  Slow Filter (SF) 8x"""
    SLOW_FILTER_4X = const(2)
    """  Slow Filter (SF) 4x"""
    SLOW_FILTER_2X = const(3)
    """ Slow Filter (SF) 2x"""

    FAST_FILTER_THRESHOLD_SLOW = const(0)
    """ Fast Filter off. Slow Filter only"""
    FAST_FILTER_THRESHOLD_6LSB = const(1)
    """ Fast Filter Threshold (FTH) 6 LSB"""
    FAST_FILTER_THRESHOLD_7LSB = const(2)
    """  Fast Filter Threshold (FTH) 7 LSB"""
    FAST_FILTER_THRESHOLD_9LSB = const(3)
    """ Fast Filter Threshold (FTH) 9 LSB"""
    FAST_FILTER_THRESHOLD_18LSB = const(4)
    """  Fast Filter Threshold (FTH) 18 LSB"""
    FAST_FILTER_THRESHOLD_21LSB = const(5)
    """ Fast Filter Threshold (FTH) 21 LSB"""
    FAST_FILTER_THRESHOLD_24LSB = const(6)
    """  Fast Filter Threshold (FTH) 24 LSB"""
    FAST_FILTER_THRESHOLD_10LSB = const(7)
    """ Fast Filter Threshold (FTH) 10 LSB"""

    def __init__(self, i2c, address=_AS5600_DEFAULT_I2C_ADDR):
        self._device = i2c_device.I2CDevice(i2c, address)

    # Output Registers

    @property
    def angle(self):
        """
        Get the current 12-bit angle value (ANGLE).

        If zero_position() and max_position(), or max_angle() has been set then
        this value is scaled to those limits.
        Else it is scaled to 0-360 degrees, with 4095 representing 360 degrees.

        :return: The current angle value as an integer.
        :rtype: int
        """
        return self._read_16(_REG_ANGLE_HI)

    @angle.setter
    def angle(self) -> NoReturn:  # noqa PLR6301
        raise AttributeError("angle is read-only")

    @property
    def raw_angle(self):
        """
        Get the current unscaled and unmodified 12-bit angle (RAWANGLE).

        :return: The current raw angle as an integer.
        :rtype: int
        """
        return self._read_16(_REG_RAW_ANGLE_HI)

    @raw_angle.setter
    def raw_angle(self) -> NoReturn:  # noqa PLR6301
        raise AttributeError("raw_angle is read-only")

    # Status Registers

    @property
    def is_magnet_too_strong(self) -> bool:
        """
        Test MH Status Bit. True if AGC minimum gain overflow, magnet too strong

        :return: True if the magnet is too strong, False otherwise.
        :rtype: bool
        """
        return bool(self._read_8(_REG_STATUS) & _STATUS_MH)

    @is_magnet_too_strong.setter
    def is_magnet_too_strong(self, value: bool) -> NoReturn:  # noqa PLR6301
        raise AttributeError("is_magnet_too_strong is read-only")

    @property
    def is_magnet_too_weak(self) -> bool:
        """
        Test ML Status Bit. True if AGC maximum gain overflow, magnet too weak

        :return: True if the magnet is too weak, False otherwise.
        :rtype: bool
        """
        return bool(self._read_8(_REG_STATUS) & _STATUS_ML)

    @is_magnet_too_weak.setter
    def is_magnet_too_weak(self, value: bool) -> NoReturn:  # noqa PLR6301
        raise AttributeError("is_magnet_too_weak is read-only")

    @property
    def is_magnet_detected(self) -> bool:
        """
        Test MD Status Bit.

        :return: True if a magnet is detected, False otherwise.
        :rtype: bool
        """
        return bool(self._read_8(_REG_STATUS) & _STATUS_MD)

    @is_magnet_detected.setter
    def is_magnet_detected(self, value: bool) -> NoReturn:  # noqa PLR6301
        raise AttributeError("is_magnet_detected is read-only")

    @property
    def gain(self) -> int:
        """
        Get the 8-bit Automatic Gain Control value (AGC).

        :return: The AGC value as an integer.
        :rtype: int
        """
        return self._read_8(_REG_AGC)

    @gain.setter
    def gain(self, value: int) -> NoReturn:  # noqa PLR6301
        raise AttributeError("gain is read-only")

    @property
    def magnitude(self) -> int:
        """
        Get the 12-bit CORDIC (Coordinate Rotation Digital Computer) magnitude (MAGNITUDE).

        :return: The magnitude value as an integer.
        :rtype: int
        """
        return self._read_16(_REG_MAGNITUDE_HI)

    @magnitude.setter
    def magnitude(self, value: int) -> NoReturn:  # noqa PLR6301
        raise AttributeError("magnitude is read-only")

    # Configuration Registers

    @property
    def zmco(self) -> int:
        """
        Get the 8-bit burn count (ZMCO).

        :return: The burn count as an integer.
        :rtype: int
        """
        return self._read_8(_REG_ZMCO)

    @zmco.setter
    def zmco(self, value: int) -> NoReturn:  # noqa PLR6301
        raise AttributeError("zmco is read-only")

    @property
    def zero_position(self) -> int:
        """
        Get and set the 12-bit zero position (ZPOS).

        For applications which do not use the full 0 to 360 degree angular range, the output
        resolution can be enhanced by programming the range which is actually used. In this case,
        the full resolution of the output is automatically scaled to the programmed angular range.
        The angular range must be greater than 18 degrees.

        Set by a combination of zero_position & max_position (ZPOS and MPOS).

        It can also be set by max_angle.

        :return: The zero position as an integer.
        :rtype: int
        """
        return self._read_16(_REG_ZPOS_HI)

    @zero_position.setter
    def zero_position(self, value: int):
        if not 0 <= value <= 4095:
            raise ValueError("Value must be between 0 & 4095")
        self._write_16(_REG_ZPOS_HI, value)

    @property
    def max_position(self) -> int:
        """
        Get and set the 12-bit maximum position (MPOS).

        For applications which do not use the full 0 to 360 degree angular range, the output
        resolution can be enhanced by programming the range which is actually used. In this case,
        the full resolution of the output is automatically scaled to the programmed angular range.
        The angular range must be greater than 18 degrees.

        Set by a combination of zero_position & max_position (ZPOS and MPOS).

        It can also be set by max_angle.

        :return: The maximum position as an integer.
        :rtype: int
        """
        return self._read_16(_REG_MPOS_HI)

    @max_position.setter
    def max_position(self, value: int):
        if not 0 <= value <= 4095:
            raise ValueError("Value must be between 0 & 4095")
        self._write_16(_REG_MPOS_HI, value)

    @property
    def max_angle(self) -> int:
        """
        Get and set the maximum anglular range (MANG) in degrees.

        For applications which do not use the full 0 to 360 degree angular range, the output
        resolution can be enhanced by programming the range which is actually used. In this case,
        the full resolution of the output is automatically scaled to the programmed angular range.
        The angular range must be greater than 18 degrees.

        It can also be set by a combination of zero_position & max_position (ZPOS and MPOS).

        :return: The maximum angle in degrees as an integer.
        :rtype: int
        """
        raw_angle = self._read_16(_REG_MANG_HI)
        angle = int((raw_angle / 4096) * 360)
        return angle

    @max_angle.setter
    def max_angle(self, value: int):
        if not 18 <= value <= 360:
            raise ValueError("Value must be between 18 & 360")

        raw_angle = int((value / 360) * 4096)
        self._write_16(_REG_MANG_HI, raw_angle)

    @property
    def power_mode(self) -> int:
        """
        Get and set the Power Mode (PM) configuration.

        Valid values: POWER_MODE_NOM, POWER_MODE_LPM1, POWER_MODE_LPM2 & POWER_MODE_LPM3

        :return: The power mode as an integer.
        :rtype: int
        """
        return self._read_conf_register(_REG_CONF_LO, _2_BITS, _BIT_POS_PM)

    @power_mode.setter
    def power_mode(self, value: int):
        if not AS5600.POWER_MODE_NOM <= value <= AS5600.POWER_MODE_LPM3:
            raise ValueError(
                f"Power Mode (PM) value must be between {AS5600.POWER_MODE_NOM} & \
                {AS5600.POWER_MODE_LPM3}"
            )
        self._write_conf_register(_REG_CONF_LO, _2_BITS, _BIT_POS_PM, value)

    @property
    def hysteresis(self) -> int:
        """
        Get and set the Hysteresis (HYST) configuration.
        Set this to avoid toggling of the output when the magnet is not moving.

        Valid values: HYSTERESIS_OFF, HYSTERESIS_1LSB, HYSTERESIS_2LSB & HYSTERESIS_3LSB

        :return: The hysteresis value as an integer.
        :rtype: int
        """
        return self._read_conf_register(_REG_CONF_LO, _2_BITS, _BIT_POS_HYST)

    @hysteresis.setter
    def hysteresis(self, value: int):
        if not AS5600.HYSTERESIS_OFF <= value <= AS5600.HYSTERESIS_3LSB:
            raise ValueError(
                f"Hysteresis (HYST) value must be between {AS5600.HYSTERESIS_OFF} &\
                {AS5600.HYSTERESIS_3LSB}"
            )
        self._write_conf_register(_REG_CONF_LO, _2_BITS, _BIT_POS_HYST, value)

    @property
    def output_stage(self) -> int:
        """
        Get and set the Output Stage configuration.
        This controls the output of pin 3 (OUT) as either an analog or PWM signal.

        Valid values: OUTPUT_STAGE_ANALOG_FULL, OUTPUT_STAGE_ANALOG_REDUCED, \
        OUTPUT_STAGE_DIGITAL_PWM

        :return: The output stage value as an integer.
        :rtype: int
        """
        return self._read_conf_register(_REG_CONF_LO, _2_BITS, _BIT_POS_OUTS)

    @output_stage.setter
    def output_stage(self, value: int):
        if not AS5600.OUTPUT_STAGE_ANALOG_FULL <= value <= AS5600.OUTPUT_STAGE_DIGITAL_PWM:
            raise ValueError(
                f"Output Stage (OUTS) value must be between {AS5600.OUTPUT_STAGE_ANALOG_FULL} \
                & {AS5600.OUTPUT_STAGE_DIGITAL_PWM}"
            )
        self._write_conf_register(_REG_CONF_LO, _2_BITS, _BIT_POS_OUTS, value)

    @property
    def pwm_frequency(self) -> int:
        """
        Get and set the PWM Frequency (PWMF) configuration.
        Sets the frequency of the PWM output.

        Ignored if output_stage is set as Analog.
        Valid values: PWM_FREQUENCY_115HZ, PWM_FREQUENCY_230HZ, PWM_FREQUENCY_460HZ \
        & PWM_FREQUENCY_920HZ

        :return: The PWM frequency value as an integer.
        :rtype: int
        """
        return self._read_conf_register(_REG_CONF_LO, _2_BITS, _BIT_POS_PWMF)

    @pwm_frequency.setter
    def pwm_frequency(self, value: int):
        if not AS5600.PWM_FREQUENCY_115HZ <= value <= AS5600.PWM_FREQUENCY_920HZ:
            raise ValueError(
                f"PWM Frequency (PWMF) value must be between {AS5600.PWM_FREQUENCY_115HZ} \
                & {AS5600.PWM_FREQUENCY_920HZ}"
            )
        self._write_conf_register(_REG_CONF_LO, _2_BITS, _BIT_POS_PWMF, value)

    @property
    def slow_filter(self) -> int:
        """
        Get and set the Slow Filter (SF) configuration.

        Valid values: SLOW_FILTER_16X, SLOW_FILTER_8X, SLOW_FILTER_4X & SLOW_FILTER_2X

        :return: The slow filter value as an integer.
        :rtype: int
        """
        return self._read_conf_register(_REG_CONF_HI, _2_BITS, _BIT_POS_SF)

    @slow_filter.setter
    def slow_filter(self, value: int):
        if not AS5600.SLOW_FILTER_16X <= value <= AS5600.SLOW_FILTER_2X:
            raise ValueError(
                f"Slow Filter (SF) value must be between {AS5600.SLOW_FILTER_16X} &\
                {AS5600.SLOW_FILTER_2X}"
            )
        self._write_conf_register(_REG_CONF_HI, _2_BITS, _BIT_POS_SF, value)

    @property
    def fast_filter(self) -> int:
        """
        Get and set the Fast Filter Threshold (FTH) configuration.

        Valid values: FAST_FILTER_THRESHOLD_SLOW, FAST_FILTER_THRESHOLD_6LSB, \
        FAST_FILTER_THRESHOLD_7LSB,

        :return: The fast filter threshold value as an integer.
        :rtype: int
        """
        return self._read_conf_register(_REG_CONF_HI, _3_BITS, _BIT_POS_FTH)

    @fast_filter.setter
    def fast_filter(self, value: int):
        if not AS5600.FAST_FILTER_THRESHOLD_SLOW <= value <= AS5600.FAST_FILTER_THRESHOLD_10LSB:
            raise ValueError(
                f"Fast Filter (FTH) value must be between {AS5600.FAST_FILTER_THRESHOLD_SLOW} \
                & {AS5600.FAST_FILTER_THRESHOLD_10LSB}"
            )
        self._write_conf_register(_REG_CONF_HI, _3_BITS, _BIT_POS_FTH, value)

    @property
    def watch_dog(self) -> bool:
        """
        Get and set the Watchdog (WD) configuration.
        True enables the watchdog.

        The watchdog configuration saves power by switching into low power mode LMP3 if the angle
        stays within the watchdog threshold of 4 LSB for at least one minute.

        :return: The watchdog value as an integer.
        :rtype: int
        """
        return bool(self._read_conf_register(_REG_CONF_HI, _1_BIT, _BIT_POS_WD))

    @watch_dog.setter
    def watch_dog(self, value: bool):
        self._write_conf_register(_REG_CONF_HI, _1_BIT, _BIT_POS_WD, int(value))

    # Burn Commands

    def burn_in_angle(self):
        """
        Perform a permanent writing of ZPOS and MPOS values to non-volatile memory.
        These are set by zero_position() and max_position().

        burn_in_angle() can only be executed sucessfully up to 3 times due to device restrictions.
        burn_in_angle() can only be executed if is_magnet_detected = True.

        zmco shows how many times ZPOS and MPOS have been permanently written.
        """
        if self.is_magnet_detected is False:
            raise RuntimeError("Magnet must be detected before burn-in can be executed")

        if self.zmco >= 3:
            raise ValueError("Burn-in can only be executed up to 3 times")

        self._write_8(_REG_BURN, _BURN_ANGLE_COMMAND)

    def burn_in_settings(self):
        """
        Perform a permanent writing of MANG and CONFIG to non-volatile memory.

        MANG is set by max_angle().

        MANG can be written only if ZPOS and MPOS have never been permanently written (zmco = 0).

        CONFIG contains the combination of all values set by the configuration methods.

        These are watch_dog, power_mode, hysteresis, output_stage, pwm_frequency,
        fast_filter & slow_filter.

        burn_in_settings() can be performed only one time due to device restrictions,
        and should be performed before burn_in_angle().
        """
        if self.zmco != 0:
            raise ValueError(
                "Can only be written if ZPOS and MPOS have never been permanently written \
                with burn_in_angle()"
            )

        self._write_8(_REG_BURN, _BURN_SETTINGS_COMMAND)

    # Internal Class Functions

    def _read_8(self, address: int) -> int:
        """
        Read and return a byte from the specified 8-bit register address.

        :param address: The register address to read from.
        :type address: int
        :return: The value read from the register.
        :rtype: int
        """
        result = bytearray(1)
        with self._device as i2c:
            i2c.write(bytes([address]))
            i2c.readinto(result)
        return result[0]

    def _write_8(self, address: int, value: int) -> int:
        """
        Write a byte to the specified 8-bit register address.

        :param address: The register address to write to.
        :type address: int
        :param value: The value to write to the register.
        :type value: int
        :return: The value written to the register.
        :rtype: int
        """
        result = bytearray(1)
        with self._device as i2c:
            i2c.write(bytes([address, value]))
            i2c.write(bytes([address]))
            i2c.readinto(result)
        return result[0]

    def _read_16(self, address: int) -> int:
        """
        Read and return a 16-bit unsigned big endian value
        from the specified 16-bit register address.

        :param address: The register address to read from.
        :type address: int
        :return: The value read from the register.
        :rtype: int
        """
        result = bytearray(2)
        with self._device as i2c:
            i2c.write(bytes([address]))
            i2c.readinto(result)
        return (result[0] << 8) | result[1]

    def _write_16(self, address: int, value: int) -> int:
        """
        Write a 16-bit big endian value to the specified 16-bit register address.

        :param address: The register address to write to.
        :type address: int
        :param value: The value to write to the register.
        :type value: int
        :return: The value written to the register.
        :rtype: int
        """
        result = bytearray(2)
        with self._device as i2c:
            i2c.write(bytes([address, (value & 0xFF00) >> 8, value & 0x00FF]))
            i2c.write(bytes([address]))
            i2c.readinto(result)
        return (result[0] << 8) | result[1]

    def _read_conf_register(self, register: int, mask: int, offset: int) -> int:
        """
        Read configuration register bits.

        :param register: The register address to read from.
        :type register: int
        :param mask: The bit mask to apply.
        :type mask: int
        :param offset: The bit offset to apply.
        :type offset: int
        :return: The value read from the register.
        :rtype: int
        """
        mask = mask << offset
        result = self._read_8(register)
        return (result & mask) >> offset

    def _write_conf_register(self, register: int, mask: int, offset: int, value: int) -> int:
        """
        Write configuration register bits.

        :param register: The register address to write to.
        :type register: int
        :param mask: The bit mask to apply.
        :type mask: int
        :param offset: The bit offset to apply.
        :type offset: int
        :param value: The value to write to the register.
        :type value: int
        :return: The value written to the register.
        :rtype: int
        """
        mask = mask << offset
        inverse_mask = ~mask & 0xFF
        current_value = self._read_8(register)
        value = (current_value & inverse_mask) | (value << offset)
        result = self._write_8(register, value)
        return (result & mask) >> offset
