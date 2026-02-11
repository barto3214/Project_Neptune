import time
from w1thermsensor import W1ThermSensor

sensor = W1ThermSensor()

while True:
    temp_c = sensor.get_temperature()
    print(f"Temperatura: {temp_c:.2f} °C")
    time.sleep(1)
