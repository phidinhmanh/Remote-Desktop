import socket
import threading
import struct
import json
import queue
from PIL import Image, ImageTk
import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox
from pynput import mouse, keyboard

# --- Utils ---
def send_msg(sock, msg):
    msg = struct.pack('>I', len(msg)) + msg
    sock.sendall(msg)

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

# --- Client Class ---
class RemoteDesktopClient:
    def __init__(self, root):
        self.root = root
        self.sock = None
        self.is_connected = False
        self.frame_queue = queue.Queue(maxsize=30)
        self.input_listeners = []

        self.init_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def init_ui(self):
        self.root.title("Remote Desktop Client")
        self.root.geometry("1024x768")

        control_frame = ttk.Frame(self.root, padding=10)
        control_frame.pack(fill=tk.X)

        self.ip_entry = self.create_labeled_entry(control_frame, "Server IP:", "127.0.0.1")
        self.port_entry = self.create_labeled_entry(control_frame, "Port:", "9999")

        self.connect_button = ttk.Button(control_frame, text="Kết nối", command=self.toggle_connection)
        self.connect_button.pack(side=tk.LEFT, padx=10)

        self.screen_label = ttk.Label(self.root, background="black")
        self.screen_label.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        self.screen_label.bind("<Button>", self.on_mouse_click)
        self.screen_label.bind("<ButtonRelease>", self.on_mouse_click)
        self.screen_label.bind("<Motion>", self.on_mouse_move)

        self.status_var = tk.StringVar(value="Sẵn sàng để kết nối.")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

    def create_labeled_entry(self, parent, label_text, default_value):
        ttk.Label(parent, text=label_text).pack(side=tk.LEFT, padx=5)
        entry = ttk.Entry(parent, width=15)
        entry.insert(0, default_value)
        entry.pack(side=tk.LEFT, padx=5)
        return entry

    def toggle_connection(self):
        if self.is_connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        try:
            host = self.ip_entry.get()
            port = int(self.port_entry.get())
            self.sock = socket.create_connection((host, port))
            self.is_connected = True
            self.status_var.set(f"Đã kết nối tới {host}:{port}")
            self.connect_button.config(text="Ngắt kết nối")

            threading.Thread(target=self.receive_frames, daemon=True).start()
            self.process_frame_queue()
            self.start_input_listeners()
            self.screen_label.focus_set()

        except Exception as e:
            messagebox.showerror("Lỗi kết nối", str(e))
            self.sock = None

    def disconnect(self):
        self.is_connected = False
        self.connect_button.config(text="Kết nối")
        self.status_var.set("Đã ngắt kết nối.")
        self.stop_input_listeners()
        if self.sock:
            self.sock.close()
            self.sock = None
        self.screen_label.config(image='')
        self.screen_label.imgtk = None
        while not self.frame_queue.empty():
            self.frame_queue.get()

    def receive_frames(self):
        while self.is_connected:
            try:
                data = recv_msg(self.sock)
                if not data:
                    break
                if not self.frame_queue.full():
                    self.frame_queue.put(data)
            except:
                break
        self.root.after(0, self.disconnect)

    def process_frame_queue(self):
        try:
            frame_data = self.frame_queue.get_nowait()
            frame_np = np.frombuffer(frame_data, np.uint8)
            frame = cv2.imdecode(frame_np, cv2.IMREAD_UNCHANGED)
            if frame is not None:
                self.update_screen(frame)
        except queue.Empty:
            pass
        if self.is_connected:
            self.root.after(15, self.process_frame_queue)

    def update_screen(self, frame):
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        img.thumbnail((self.screen_label.winfo_width(), self.screen_label.winfo_height()), Image.Resampling.LANCZOS)
        img_tk = ImageTk.PhotoImage(image=img)
        self.screen_label.imgtk = img_tk
        self.screen_label.config(image=img_tk)

    def send_event(self, data):
        if self.is_connected and self.sock:
            try:
                send_msg(self.sock, json.dumps(data).encode('utf-8'))
            except:
                self.root.after(0, self.disconnect)

    def start_input_listeners(self):
        self.input_listeners = [
            mouse.Listener(on_click=self.on_pynput_mouse, on_scroll=self.on_pynput_scroll),
            keyboard.Listener(on_press=lambda k: self.send_key_event(k, 'press'),
                              on_release=lambda k: self.send_key_event(k, 'release'))
        ]
        for listener in self.input_listeners:
            listener.start()

    def stop_input_listeners(self):
        for listener in self.input_listeners:
            listener.stop()
        self.input_listeners = []

    def on_mouse_click(self, event):
        button_map = {1: 'left', 2: 'middle', 3: 'right'}
        pressed = event.type == tk.EventType.ButtonPress
        rel_x = event.x / max(1, self.screen_label.winfo_width())
        rel_y = event.y / max(1, self.screen_label.winfo_height())
        self.send_event({'type': 'mouse', 'action': 'click', 'x': rel_x, 'y': rel_y, 'button': button_map.get(event.num), 'pressed': pressed})

    def on_mouse_move(self, event):
        rel_x = event.x / max(1, self.screen_label.winfo_width())
        rel_y = event.y / max(1, self.screen_label.winfo_height())
        self.send_event({'type': 'mouse', 'action': 'move', 'x': rel_x, 'y': rel_y})

    def get_relative_coords(self, abs_x, abs_y):
        win_x, win_y = self.screen_label.winfo_rootx(), self.screen_label.winfo_rooty()
        win_w, win_h = self.screen_label.winfo_width(), self.screen_label.winfo_height()
        if win_w == 0 or win_h == 0:
            return None
        rel_x, rel_y = (abs_x - win_x) / win_w, (abs_y - win_y) / win_h
        return (rel_x, rel_y) if 0 <= rel_x <= 1 and 0 <= rel_y <= 1 else None

    def on_pynput_mouse(self, x, y, button, pressed):
        coords = self.get_relative_coords(x, y)
        if coords:
            self.send_event({'type': 'mouse', 'action': 'click', 'x': coords[0], 'y': coords[1], 'button': button.name, 'pressed': pressed})

    def on_pynput_scroll(self, x, y, dx, dy):
        coords = self.get_relative_coords(x, y)
        if coords:
            self.send_event({'type': 'mouse', 'action': 'scroll', 'x': coords[0], 'y': coords[1], 'dx': dx, 'dy': dy})

    def send_key_event(self, key, action):
        if self.root.focus_get() is not self.screen_label:
            return
        key_str = key.name if isinstance(key, keyboard.Key) else key.char
        if key_str:
            self.send_event({'type': 'keyboard', 'action': action, 'key': key_str})

    def on_close(self):
        if self.is_connected:
            self.disconnect()
        self.root.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    app = RemoteDesktopClient(root)
    root.mainloop()
