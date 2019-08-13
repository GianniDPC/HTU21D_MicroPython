from htu21d import HTU21D
import utime

htu21d = HTU21D()

# do not forget to initialize
htu21d.init()

# set resolution
htu21d.set_resolution(htu21d.UserRegister.USER_REGISTER_RESOLUTION_RH12_TEMP14)

if not htu21d.heater_enabled:
    htu21d.toggle_heater()

print("Heater enabled: %r" % htu21d.heater_enabled)

while True:
    print("Temperature in Celsius: %.2f °C" % htu21d.read_temp(htu21d.Mode.NO_HOLD,
                                                          htu21d.UNIT.Celsius))
    print("Temperature in Fahrenheit: %.2f °F" % htu21d.read_temp(htu21d.Mode.NO_HOLD,
                                                               htu21d.UNIT.Fahrenheit))
    print("Humidity: %.2f %%" % htu21d.read_humidity(htu21d.Mode.NO_HOLD))
    utime.sleep(1)
