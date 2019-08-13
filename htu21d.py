import utime


class Mode(object):
    HOLD = 0
    NO_HOLD = 1


class Registers(object):
    """ Read temperature register. """
    HTU21DF_I2CADDR = 0x40

    """ Read temperature register -> HOLD MODE """
    HTU21DF_READTEMP_H = 0xE3

    """ Read temperature register -> NO HOLD MODE """
    HTU21DF_READTEMP_NH = 0xF3

    """ Read humidity register -> HOLD MODE """
    HTU21DF_READHUM_H = 0xE5

    """ Read humidity register -> NO HOLD MODE """
    HTU21DF_READHUM_NH = 0xF5

    """ Write register command """
    HTU21DF_WRITEREG = 0xE6

    """ Read register command. """
    HTU21DF_READREG = 0xE7

    """ Reset command. """
    HTU21DF_RESET = 0xFE


class UserRegister(object):
    USER_REGISTER_RESOLUTION_MASK = 0x81

    """" 14-bit precision """
    USER_REGISTER_RESOLUTION_RH12_TEMP14 = 0x00

    """" 13-bit precision """
    USER_REGISTER_RESOLUTION_RH10_TEMP13 = 0x80

    """" 12-bit precision """
    USER_REGISTER_RESOLUTION_RH8_TEMP12 = 0x01

    """" 11-bit precision """
    USER_REGISTER_RESOLUTION_RH11_TEMP11 = 0x81

    USER_REGISTER_END_OF_BATTERY = 0x40

    USER_REGISTER_HEATER_ENABLED = 0x04

    USER_REGISTER_DISABLE_OTP_RELOAD = 0x02


class ENUM_UNIT:
    Celsius = 0
    Fahrenheit = 1


def _process_data(data, enable_crc):
    # Check if length is 3 bytes
    if len(data) != 3:
        return 0.0

    # Shift first byte 8 (MSB) places to create 16 bit value
    # OR with last byte (LSB) to create final value
    raw = (data[0] << 8) | data[1]

    if enable_crc:
        # CRC check data
        if not _crc_check(raw, data[2]):
            raise ValueError("CRC does not match!")

    # MASK to set last 2 status bits zo zero
    raw_masked = raw & 0xFFFC

    return raw_masked


def _crc_check(raw, checksum):
    remainder = raw << 8
    remainder |= checksum

    divisor = 0x988000

    for i in range(0, 16):
        if remainder & 1 << (23 - i):
            remainder ^= divisor

        divisor >>= 1

    return True if remainder == 0 else False


class HTU21D(object):
    Mode = Mode
    UserRegister = UserRegister
    UNIT = ENUM_UNIT

    def __init__(self):
        self.i2c = None

    def init(self, scl=22, sda=21, freq=100000):
        """ Initialize I2C and chip. """
        from machine import I2C, Pin

        self.i2c = I2C(0, scl=Pin(scl), sda=Pin(sda), freq=freq)

        self.reset()

        self.i2c.writeto(Registers.HTU21DF_I2CADDR,
                         bytearray([Registers.HTU21DF_READREG]))

        res = self.i2c.readfrom(Registers.HTU21DF_I2CADDR, 1)[0]

        return True if res == 0x2 else False

    def set_resolution(self, resolution):
        """ Set resolution of chip. """

        # Go get the current register state
        read_reg = self.read_user_register()

        # Turn off the resolution bits
        read_reg &= 0x7e

        # Turn off all other bits but resolution bits
        resolution &= 0x81

        # Mask in the requested resolution bits
        read_reg |= resolution

        # Request a write to user register
        self.write_user_register(read_reg)

    def toggle_heater(self):
        """ The heater is intended to be used for functionality diagnosis:
        relative humidity drops upon rising temperature. """

        # Go get the current register state
        read_reg = self.read_user_register()

        # Toggle heater bit
        read_reg ^= 0x4

        # Request a write to user register
        self.write_user_register(read_reg)

    def toggle_otp_reload(self):
        """ OTP reload is a safety feature and load the entire OTP settings to the register,
        with the exception of the heater bit, before every measurement. """

        # Go get the current register state
        read_reg = self.read_user_register()

        # Toggle heater bit
        read_reg ^= 0x2

        # Request a write to user register
        self.write_user_register(read_reg)

    def read_user_register(self):
        self.i2c.writeto(Registers.HTU21DF_I2CADDR,
                         bytearray([Registers.HTU21DF_READREG]))

        read_reg = self.i2c.readfrom(Registers.HTU21DF_I2CADDR, 1)[0]

        return read_reg

    def write_user_register(self, value):
        self.i2c.writevto(Registers.HTU21DF_I2CADDR,
                          [bytearray([Registers.HTU21DF_WRITEREG]),
                           bytearray([value])])

    def read_temp(self, mode=Mode.HOLD, unit=UNIT.Celsius, enable_crc=True):
        self.i2c.writeto(Registers.HTU21DF_I2CADDR,
                         bytearray([Registers.HTU21DF_READTEMP_H
                                    if mode == Mode.HOLD
                                    else Registers.HTU21DF_READTEMP_NH]))

        utime.sleep_ms(50)

        # Data consists of 3 bytes
        # 1. MSB 2. LSB 3. CRC
        data = self.i2c.readfrom(Registers.HTU21DF_I2CADDR, 3)

        raw = _process_data(data, enable_crc)

        temp = -46.85 + (175.72 * raw / 65536)

        if unit == self.UNIT.Celsius:
            return temp
        elif unit == self.UNIT.Fahrenheit:
            return (temp * 9.0) / 5.0 + 32
        else:
            raise NotImplementedError("This unit is not implemented.")

    def read_humidity(self, mode=Mode.HOLD, enable_crc=True):
        """ Read humidity from sensor. """
        self.i2c.writeto(Registers.HTU21DF_I2CADDR,
                         bytearray([Registers.HTU21DF_READHUM_H
                                    if mode == Mode.HOLD
                                    else Registers.HTU21DF_READHUM_NH]))

        utime.sleep_ms(50)

        # Data consists of 3 bytes
        # 1. MSB 2. LSB 3. CRC
        data = self.i2c.readfrom(Registers.HTU21DF_I2CADDR, 3)

        raw = _process_data(data, enable_crc)

        return -6 + (125.0 * raw / 65536)

    @property
    def end_of_battery(self):
        """ The “End of Battery” alert/status is activated when
        the battery power falls below 2.25V. """

        read_reg = self.read_user_register()
        return True if (read_reg & UserRegister.USER_REGISTER_END_OF_BATTERY) else False

    @property
    def heater_enabled(self):
        """ Check if heater enabled. """
        read_reg = self.read_user_register()
        return True if (read_reg & UserRegister.USER_REGISTER_HEATER_ENABLED) else False

    @property
    def otp_reload_enabled(self):
        """ Check if otp reload enabled. """
        read_reg = self.read_user_register()
        return False if (read_reg & UserRegister.USER_REGISTER_DISABLE_OTP_RELOAD) else True

    def reset(self):
        """ Reset chip. """
        self.i2c.writeto(Registers.HTU21DF_I2CADDR,
                         bytearray([Registers.HTU21DF_RESET]))

        utime.sleep_ms(15)
