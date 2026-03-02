#!/usr/bin/env python3
"""
OBRÓT KARUZELI NA PODSTAWIE TICKÓW ENKODERA
Obraca karuzelę o zadaną liczbę ticków, zlicza kroki silnika.

Podłączenie HEDL-5540:
  Pin 2 (RED)    → 3.3V
  Pin 3 (ORANGE) → GND
  Pin 5 (GREEN)  → GPIO 16 (A)
  Pin 7 (VIOLET) → GPIO 20 (B)
  Pin 9 (WHITE)  → GPIO 21 (I)
"""

import RPi.GPIO as GPIO
import time
import threading

# ── Enkoder ───────────────────────────────────────────────
ENC_A = 16
ENC_B = 20
ENC_I = 21

# ── Silnik krokowy ─────────────────────────────────────────
STEP_IN1 = 17
STEP_IN2 = 27
STEP_IN3 = 22
STEP_IN4 = 23

STEP_DELAY = 0.002  # opóźnienie między krokami (sekundy)

HALF_STEP_SEQ = [
    [1, 0, 0, 0],
    [1, 1, 0, 0],
    [0, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 0],
    [0, 0, 1, 1],
    [0, 0, 0, 1],
    [1, 0, 0, 1]
]

# ── Liczniki ───────────────────────────────────────────────
tick_count  = 0
step_count  = 0
_tick_lock  = threading.Lock()

# ── GPIO setup ────────────────────────────────────────────
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

GPIO.setup(ENC_A,    GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(ENC_B,    GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(ENC_I,    GPIO.IN, pull_up_down=GPIO.PUD_UP)

GPIO.setup(STEP_IN1, GPIO.OUT)
GPIO.setup(STEP_IN2, GPIO.OUT)
GPIO.setup(STEP_IN3, GPIO.OUT)
GPIO.setup(STEP_IN4, GPIO.OUT)


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


def set_step(w1, w2, w3, w4):
    GPIO.output(STEP_IN1, w1)
    GPIO.output(STEP_IN2, w2)
    GPIO.output(STEP_IN3, w3)
    GPIO.output(STEP_IN4, w4)


def rotate_by_ticks(target_ticks, direction=1, timeout=10.0):
    """
    Obraca karuzelę aż enkoder zliczy target_ticks ticków.
    Zwraca (ticki_faktyczne, kroki_faktyczne).
    
    direction: 1 = do przodu, -1 = do tyłu
    timeout: max czas w sekundach
    """
    global tick_count, step_count

    with _tick_lock:
        tick_count = 0
    step_count = 0

    seq_len   = len(HALF_STEP_SEQ)
    seq_range = range(seq_len)[::direction]
    start     = time.time()

    while True:
        # Sprawdź czy osiągnęliśmy cel
        with _tick_lock:
            current_ticks = abs(tick_count)

        if current_ticks >= target_ticks:
            break

        # Sprawdź timeout
        if time.time() - start > timeout:
            print(f"[WARN] Timeout! Osiągnięto {current_ticks}/{target_ticks} ticków")
            break

        # Wykonaj jeden krok silnika
        for s in seq_range:
            set_step(*HALF_STEP_SEQ[s])
            time.sleep(STEP_DELAY)

        step_count += 1

    # Wyłącz cewki
    set_step(0, 0, 0, 0)

    with _tick_lock:
        final_ticks = abs(tick_count)

    return final_ticks, step_count


def main():
    global tick_count

    print("=" * 50)
    print("  OBRÓT NA PODSTAWIE TICKÓW ENKODERA")
    print("=" * 50)
    print()

    try:
        while True:
            print("Opcje:")
            print("  1 - Obróć o zadaną liczbę ticków")
            print("  2 - Test: obróć 5 razy i uśrednij ticki na pozycję")
            print("  r - Reset licznika")
            print("  q - Wyjście")
            print()

            choice = input("Wybór: ").strip().lower()

            if choice == '1':
                try:
                    target = int(input("Ile ticków? "))
                    print(f"\nObracam o {target} ticków...")
                    ticks, steps = rotate_by_ticks(target)
                    print(f"\n── Wynik ──────────────────────")
                    print(f"  Cel           : {target} ticków")
                    print(f"  Faktyczne ticki: {ticks}")
                    print(f"  Kroki silnika  : {steps}")
                    print(f"  Błąd           : {ticks - target} ticków")
                    print()
                except ValueError:
                    print("Nieprawidłowa liczba\n")

            elif choice == '2':
                try:
                    target = int(input("Ile ticków na pozycję (zacznij od 165): "))
                    results = []
                    print(f"\nTesruję 5 obrotów po {target} ticków...")
                    for i in range(5):
                        ticks, steps = rotate_by_ticks(target)
                        results.append((ticks, steps))
                        print(f"  Obrót {i+1}: {ticks} ticków, {steps} kroków")
                        time.sleep(0.3)
                    avg_steps = sum(s for _, s in results) / len(results)
                    avg_ticks = sum(t for t, _ in results) / len(results)
                    print(f"\n── Średnia ────────────────────")
                    print(f"  Śr. ticki : {avg_ticks:.1f}")
                    print(f"  Śr. kroki : {avg_steps:.1f}")
                    print(f"  → Użyj TICKS_PER_POSITION = {target} w master.py")
                    print(f"  → STEPS_PER_POSITION ≈ {int(avg_steps)}")
                    print()
                except ValueError:
                    print("Nieprawidłowa liczba\n")

            elif choice == 'r':
                with _tick_lock:
                    tick_count = 0
                print("Reset\n")

            elif choice == 'q':
                break

    except KeyboardInterrupt:
        pass
    finally:
        set_step(0, 0, 0, 0)
        GPIO.cleanup()
        print("\nZamknięto")


if __name__ == '__main__':
    main()