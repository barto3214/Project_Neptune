#!/usr/bin/env python3
"""
KAMERA ŁÓDKA - MJPEG Stream Server
Raspberry Pi + ArduCam 64MP (CSI)

Uruchomienie:
    python3 camera_stream.py

Stream: http://<IP_LODKI>:8080/stream
Snapshot: http://<IP_LODKI>:8080/snapshot
Podgląd w przeglądarce: http://<IP_LODKI>:8080/
"""

import subprocess
import threading
import time
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer

STREAM_PORT  = 8080
WIDTH        = 1280
HEIGHT       = 720
FRAMERATE    = 30
JPEG_QUALITY = 70

frame_lock  = threading.Lock()
last_frame  = None
frame_event = threading.Event()


def capture_loop():
    global last_frame

    cmd = [
        "libcamera-vid",
        "--width",     str(WIDTH),
        "--height",    str(HEIGHT),
        "--framerate", str(FRAMERATE),
        "--codec",     "mjpeg",
        "--quality",   str(JPEG_QUALITY),
        "--timeout",   "0",
        "--nopreview",
        "-o", "-",
    ]

    print(f"[CAM] Start: {WIDTH}x{HEIGHT} @ {FRAMERATE}fps")

    while True:
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0
            )
            print("[CAM] Kamera aktywna")

            buf = b""
            while True:
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                buf += chunk

                while True:
                    start = buf.find(b"\xff\xd8")
                    end   = buf.find(b"\xff\xd9", start + 2)
                    if start == -1 or end == -1:
                        break
                    jpeg = buf[start:end + 2]
                    buf  = buf[end + 2:]
                    with frame_lock:
                        last_frame = jpeg
                    frame_event.set()
                    frame_event.clear()

        except Exception as e:
            print(f"[CAM] Błąd: {e} — restart za 2s")
            time.sleep(2)


class MJPEGHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/stream":
            self._serve_stream()
        elif self.path == "/snapshot":
            self._serve_snapshot()
        elif self.path == "/":
            self._serve_index()
        else:
            self.send_error(404)

    def _serve_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=--frame")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        print(f"[HTTP] Klient: {self.client_address[0]}")

        try:
            while True:
                frame_event.wait(timeout=1.0)
                with frame_lock:
                    frame = last_frame
                if frame is None:
                    continue
                header = (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(frame)).encode() + b"\r\n"
                    b"\r\n"
                )
                self.wfile.write(header + frame + b"\r\n")
                self.wfile.flush()

        except (BrokenPipeError, ConnectionResetError):
            print(f"[HTTP] Rozłączono: {self.client_address[0]}")
        except Exception as e:
            print(f"[HTTP] Błąd: {e}")

    def _serve_snapshot(self):
        with frame_lock:
            frame = last_frame
        if frame is None:
            self.send_error(503, "Brak klatki")
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(frame)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(frame)

    def _serve_index(self):
        html = (
            f"<html><body style='background:#000;color:#fff;text-align:center'>"
            f"<h2>Lodka CAM {WIDTH}x{HEIGHT}@{FRAMERATE}fps</h2>"
            f"<img src='/stream'>"
            f"</body></html>"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "?.?.?.?"


def main():
    print("=" * 50)
    print("  KAMERA LODKA - MJPEG Stream")
    print("=" * 50)

    cam_thread = threading.Thread(target=capture_loop, daemon=True)
    cam_thread.start()

    print("[HTTP] Czekam na pierwszą klatkę...")
    for _ in range(50):
        if last_frame is not None:
            break
        time.sleep(0.1)

    server = HTTPServer(("0.0.0.0", STREAM_PORT), MJPEGHandler)
    server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    ip = get_local_ip()
    print(f"[HTTP] Serwer na porcie {STREAM_PORT}")
    print(f"[HTTP] Stream:    http://{ip}:{STREAM_PORT}/stream")
    print(f"[HTTP] Snapshot:  http://{ip}:{STREAM_PORT}/snapshot")
    print(f"[HTTP] Przeglądarka: http://{ip}:{STREAM_PORT}/")
    print("Ctrl+C aby zatrzymać")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nZatrzymano")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()