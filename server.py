import socket
import threading
import time
import struct
import json
import traceback
from mss import mss
from PIL import Image
import numpy as np
import cv2
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController
import tkinter as tk
from tkinter import ttk
import os


class RemoteInputHandler:
    def __init__(self):
        self.mouse = MouseController()
        self.keyboard = KeyboardController()
        with mss() as sct:
            monitor = sct.monitors[1]
            self.screen_width = monitor["width"]
            self.screen_height = monitor["height"]

    def process_event(self, event_data):
        try:
            event = json.loads(event_data)
            if event.get("type") == "mouse":
                self._handle_mouse(event)
            elif event.get("type") == "keyboard":
                self._handle_keyboard(event)
        except Exception as e:
            print(f"[Error] Event processing: {e}")

    def _handle_mouse(self, event):
        x = int(event['x'] * self.screen_width)
        y = int(event['y'] * self.screen_height)
        self.mouse.position = (x, y)

        action = event.get("action")
        if action == "click":
            button = Button[event['button']]
            if event['pressed']:
                self.mouse.press(button)
            else:
                self.mouse.release(button)
        elif action == "scroll":
            self.mouse.scroll(event['dx'], event['dy'])

    def _handle_keyboard(self, event):
        key_str = event['key']
        action = event.get("action")

        key = getattr(Key, key_str, key_str)

        if action == "press":
            self.keyboard.press(key)
        elif action == "release":
            self.keyboard.release(key)


def send_msg(sock, msg):
    sock.sendall(struct.pack('>I', len(msg)) + msg)

def recv_msg(sock):
    raw_msglen = recvall(sock, 4)
    if not raw_msglen:
        return None
    msglen = struct.unpack('>I', raw_msglen)[0]
    return recvall(sock, msglen)

def recvall(sock, n):
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data


class RemoteDesktopServer:
    def __init__(self, host='0.0.0.0', port=9999):
        self.host = host
        self.port = port
        self.server_socket = None
        self.client_conn = None
        self.running = False
        self.input_handler = RemoteInputHandler()
        self.capture_thread = None
        self.receive_thread = None
        self.ui = None

    def start(self):
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)
        self._update_status(f"Listening on {self.host}:{self.port}")
        threading.Thread(target=self._accept_clients, daemon=True).start()

    def _accept_clients(self):
        while self.running:
            try:
                self.client_conn, addr = self.server_socket.accept()
                self._update_status(f"Connected to {addr}")

                self.capture_thread = threading.Thread(target=self._stream_screen, daemon=True)
                self.receive_thread = threading.Thread(target=self._receive_events, daemon=True)

                self.capture_thread.start()
                self.receive_thread.start()
            except Exception as e:
                self._update_status(f"[Error] Accepting client: {e}")

    def _stream_screen(self):
        with mss() as sct:
            monitor = sct.monitors[1]
            while self.running and self.client_conn:
                try:
                    start = time.time()
                    img = sct.grab(monitor)
                    pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
                    frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                    _, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                    send_msg(self.client_conn, buffer.tobytes())
                    time.sleep(max(0, (1/30) - (time.time() - start)))
                except Exception as e:
                    self._update_status(f"[Error] Streaming: {e}")
                    traceback.print_exc()
                    break

    def _receive_events(self):
        while self.running and self.client_conn:
            try:
                data = recv_msg(self.client_conn)
                if data is None:
                    self._update_status("Client disconnected")
                    break
                threading.Thread(target=self.input_handler.process_event, args=(data.decode(),), daemon=True).start()
            except Exception as e:
                self._update_status(f"[Error] Receiving input: {e}")
                traceback.print_exc()
                break

    def stop(self):
        self.running = False
        if self.client_conn:
            try: self.client_conn.close()
            except: pass
        if self.server_socket:
            try: self.server_socket.close()
            except: pass
        self._update_status("Server stopped")

    def _update_status(self, msg):
        print(msg)
        if self.ui and hasattr(self, 'status_label'):
            self.ui.after(0, lambda: self.status_label.config(text=msg))

    def _on_close(self):
        self.stop()
        if self.ui:
            self.ui.destroy()

    def run_ui(self):
        self.ui = tk.Tk()
        self.ui.title("Remote Desktop Server")
        self.ui.geometry("400x180")
        self.ui.resizable(False, False)

        frame = ttk.Frame(self.ui, padding=10)
        frame.pack(fill="both", expand=True)

        self.status_label = ttk.Label(frame, text="Server not started", wraplength=380)
        self.status_label.pack(pady=10)

        ttk.Button(frame, text="Start Server", command=self.start).pack(pady=5)
        ttk.Button(frame, text="Stop Server", command=self._on_close).pack(pady=5)

        self.ui.protocol("WM_DELETE_WINDOW", self._on_close)
        self.ui.mainloop()


if __name__ == '__main__':
    server = RemoteDesktopServer()
    server.run_ui()
