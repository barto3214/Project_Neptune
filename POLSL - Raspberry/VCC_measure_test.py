import board
import busio
import time
from adafruit_ina219 import INA219
from adafruit_ads1x15.ads1015 import ADS1015
from adafruit_ads1x15.analog_in import AnalogIn

i2c = busio.I2C(board.SCL, board.SDA)
ina = INA219(i2c)
ads = ADS1015(i2c)
ch0 = AnalogIn(ads, 0)

while True:
    voltage = ina.bus_voltage
    current = ina.current

    
    if abs(current) > 1000:
        print(f"Napięcie: {voltage:.2f} V  [prąd: szum, ignoruję]")
    else:
        print(f"Napięcie: {voltage:.2f} V  Prąd: {current:.1f} mA")

    time.sleep(1)