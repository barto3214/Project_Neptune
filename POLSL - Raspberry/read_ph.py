import time
import board
import busio
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS1115(i2c)
chan = AnalogIn(ads, 0)

# WARTOŚCI KALIBRACYJNE
CAL_PH1 = 4.1
CAL_VOLTAGE1 = 0.88

CAL_PH2 = 9.1
CAL_VOLTAGE2 = 1.43

slope = (CAL_PH2 - CAL_PH1) / (CAL_VOLTAGE2 - CAL_VOLTAGE1)
offset = CAL_PH1 - slope * CAL_VOLTAGE1

def voltage_to_ph(voltage):
    return slope * voltage + offset

print("=== POMIAR pH ===")
print(f"Kalibracja: {CAL_PH1} pH @ {CAL_VOLTAGE1}V, {CAL_PH2} pH @ {CAL_VOLTAGE2}V")
print(f"Nachylenie: {slope:.2f} pH/V\n")

try:
    while True:
        voltage = chan.voltage
        ph = voltage_to_ph(voltage)
        print(f"pH: {ph:.2f}  ", end='\r')
        time.sleep(0.5)
except KeyboardInterrupt:
    print("\n\nZakończono")