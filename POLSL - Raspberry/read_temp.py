import time

SENSOR_ID = '28-000010aa60a2'
device_file = f'/sys/bus/w1/devices/{SENSOR_ID}/w1_slave'

def read_temp():
    with open(device_file, 'r') as f:
        lines = f.readlines()
    
    if len(lines) >= 2 and 'YES' in lines[0]:
        temp_pos = lines[1].find('t=')
        if temp_pos != -1:
            temp_string = lines[1][temp_pos+2:].strip()
            temp_c = float(temp_string) / 1000.0
            return temp_c
    return None

print("=== POMIAR TEMPERATURY DS18B20 ===")

try:
    while True:
        temp = read_temp()
        if temp is not None:
            print(f"Temperatura: {temp:.2f}°C  ", end='\r')
        else:
            print("Błąd odczytu...       ", end='\r')
        time.sleep(0.5)
except KeyboardInterrupt:
    print("\n\nZakończono pomiar temperatury")