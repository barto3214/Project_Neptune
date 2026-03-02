#!/usr/bin/env python3
"""
Kalibracja karuzeli z silnikiem krokowym i serwem,
obroty liczone na podstawie ticków enkodera.
"""

import RPi.GPIO as GPIO
import time
import threading

# === PINY ===
STEP_IN1 = 17
STEP_IN2 = 27
STEP_IN3 = 22
STEP_IN4 = 23

SERVO_PIN = 18

ENC_A = 16
ENC_B = 20
ENC_I = 21

STEP_DELAY = 0.002  # opóźnienie kroków

# === SEKWENCJA KROKÓW ===
HALF_STEP_SEQ = [
    [1,0,0,0],
    [1,1,0,0],
    [0,1,0,0],
    [0,1,1,0],
    [0,0,1,0],
    [0,0,1,1],
    [0,0,0,1],
    [1,0,0,1]
]

# === LICZNIKI I LOCKI ===
tick_count = 0
step_count = 0
_tick_lock = threading.Lock()

# === GPIO ===
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

GPIO.setup(STEP_IN1, GPIO.OUT)
GPIO.setup(STEP_IN2, GPIO.OUT)
GPIO.setup(STEP_IN3, GPIO.OUT)
GPIO.setup(STEP_IN4, GPIO.OUT)

GPIO.setup(SERVO_PIN, GPIO.OUT)
servo_pwm = GPIO.PWM(SERVO_PIN, 50)
servo_pwm.start(0)

GPIO.setup(ENC_A, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(ENC_B, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(ENC_I, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# === OBSŁUGA ENKODERA ===
def encoder_callback(channel):
    global tick_count
    a = GPIO.input(ENC_A)
    b = GPIO.input(ENC_B)
    with _tick_lock:
        if a != b:
            tick_count += 1
        else:
            tick_count -= 1

GPIO.add_event_detect(ENC_A, GPIO.BOTH, callback=encoder_callback)

# === FUNKCJE ===
def set_step(w1, w2, w3, w4):
    GPIO.output(STEP_IN1, w1)
    GPIO.output(STEP_IN2, w2)
    GPIO.output(STEP_IN3, w3)
    GPIO.output(STEP_IN4, w4)

def move_servo(duty):
    servo_pwm.ChangeDutyCycle(duty)
    time.sleep(0.5)
    servo_pwm.ChangeDutyCycle(0)

def rotate_by_ticks(target_ticks, direction=1, timeout=10.0):
    global tick_count, step_count
    with _tick_lock:
        tick_count = 0
    step_count = 0

    seq_len   = len(HALF_STEP_SEQ)
    seq_range = range(seq_len)[::direction]
    start     = time.time()

    while True:
        with _tick_lock:
            current_ticks = abs(tick_count)
        if current_ticks >= target_ticks:
            break
        if time.time() - start > timeout:
            print(f"[WARN] Timeout! Osiągnięto {current_ticks}/{target_ticks} ticków")
            break
        for s in seq_range:
            set_step(*HALF_STEP_SEQ[s])
            time.sleep(STEP_DELAY)
        step_count += 1

    set_step(0,0,0,0)
    with _tick_lock:
        final_ticks = abs(tick_count)
    return final_ticks, step_count

# === MENU ===
def main():
    servo_up = 11.7
    servo_down = 2.5
    ticks_per_pos = 164  # przykładowa wartość, można kalibrować

    try:
        while True:
            print("\nKALIBRACJA KARUZELI")
            print("1 - Kalibracja serwa")
            print("2 - Kalibracja silnika (ticki)")
            print("3 - Test pełnej sekwencji")
            print("0 - Wyjście")

            choice = input("Wybierz opcję: ").strip()

            if choice == '1':
                print("\n=== SERVO ===")
                print("Zakres duty: 2.5-12.5%")
                while True:
                    duty = input("Duty cycle lub q: ").strip()
                    if duty.lower() == 'q':
                        break
                    try:
                        val = float(duty)
                        move_servo(val)
                        resp = input("Zapisać jako (u)p/(d)own? ").strip().lower()
                        if resp == 'u':
                            servo_up = val
                            print(f"SERVO_UP = {val}")
                        elif resp == 'd':
                            servo_down = val
                            print(f"SERVO_DOWN = {val}")
                    except ValueError:
                        print("Nieprawidłowa wartość")

            elif choice == '2':
                print("\n=== SILNIK ===")
                while True:
                    ticks = input(f"Ile ticków na pozycję (akt. {ticks_per_pos}) lub q: ").strip()
                    if ticks.lower() == 'q':
                        break
                    try:
                        val = int(ticks)
                        t, s = rotate_by_ticks(val)
                        print(f"Faktyczne ticki: {t}, kroki silnika: {s}")
                        ticks_per_pos = val
                        done = input("Pozycja OK? (y/n): ").strip().lower()
                        if done == 'y':
                            break
                    except ValueError:
                        print("Nieprawidłowa wartość")

            elif choice == '3':
                print("\n=== TEST SEKWENCJI ===")
                print("1. Igła w dół")
                move_servo(servo_down)
                time.sleep(1)
                print("2. Pauza")
                time.sleep(2)
                print("3. Igła w górę")
                move_servo(servo_up)
                time.sleep(1)
                print("4. Obrót karuzeli")
                rotate_by_ticks(ticks_per_pos)
                print("✓ Sekwencja zakończona")

            elif choice == '0':
                break

            else:
                print("Nieprawidłowa opcja")

    except KeyboardInterrupt:
        pass
    finally:
        set_step(0,0,0,0)
        move_servo(servo_up)
        servo_pwm.stop()
        GPIO.cleanup()
        print("Wyłączono GPIO")

if __name__ == '__main__':
    main()