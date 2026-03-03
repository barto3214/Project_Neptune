import serial

PORT = '/dev/serial0'
BAUDRATE = 9600


def convert_to_decimal(raw_value, direction):
    """
    Konwersja z formatu NMEA (ddmm.mmmm)
    na stopnie dziesiętne
    """
    if raw_value == "":
        return None

    # pierwsze 2 znaki = stopnie (dla szerokości)
    degrees = float(raw_value[:2])
    minutes = float(raw_value[2:])
    decimal = degrees + (minutes / 60)

    if direction in ['S', 'W']:
        decimal *= -1

    return decimal


ser = serial.Serial(PORT, BAUDRATE, timeout=1)

print("Czekam na FIX GPS...")

while True:
    line = ser.readline().decode('ascii', errors='replace')

    if line.startswith("$GNGGA"):
        parts = line.split(",")

        fix_quality = parts[6]

        if fix_quality != "0":  # jeśli jest FIX
            raw_lat = parts[2]
            lat_dir = parts[3]
            raw_lon = parts[4]
            lon_dir = parts[5]

            latitude = convert_to_decimal(raw_lat, lat_dir)
            longitude = convert_to_decimal(raw_lon, lon_dir)

            print(f"Szerokość: {latitude}")
            print(f"Długość:  {longitude}")
            print("-" * 40)