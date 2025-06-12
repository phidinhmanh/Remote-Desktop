import socket
import threading
import time
import struct
import json
from mss import mss
from PIL import Image
import numpy as np
import cv2
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController
import tkinter as tk
from tkinter import ttk
import traceback

# --- Trình xử lý điều khiển từ xa ---
class RemoteInputHandler:
    """Xử lý các sự kiện chuột và bàn phím từ xa."""
    def __init__(self):
        self.mouse = MouseController()
        self.keyboard = KeyboardController()
        # Lấy kích thước màn hình để tính toán tọa độ tương đối
        with mss() as sct:
            monitor = sct.monitors[1]
            self.screen_width = monitor["width"]
            self.screen_height = monitor["height"]

    def process_event(self, event_data):
        """Phân tích và thực thi một sự kiện điều khiển."""
        try:
            event = json.loads(event_data)
            event_type = event.get("type")

            if event_type == "mouse":
                self.handle_mouse_event(event)
            elif event_type == "keyboard":
                self.handle_keyboard_event(event)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Lỗi xử lý dữ liệu sự kiện: {e}")

    def handle_mouse_event(self, event):
        """Xử lý các sự kiện chuột."""
        # Chuyển đổi tọa độ tương đối (0.0 - 1.0) thành tọa độ tuyệt đối trên màn hình
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

    def handle_keyboard_event(self, event):
        """Xử lý các sự kiện bàn phím."""
        key_str = event['key']
        action = event.get("action")

        try:
            # Cố gắng xử lý các phím đặc biệt từ pynput.keyboard.Key
            key = getattr(Key, key_str)
        except AttributeError:
            # Nếu không phải phím đặc biệt, nó là một ký tự thông thường
            key = key_str

        if action == 'press':
            self.keyboard.press(key)
        elif action == 'release':
            self.keyboard.release(key)

# --- Chức năng Mạng ---
def send_msg(sock, msg):
    """Gửi một thông điệp với tiền tố là độ dài của nó."""
    msg = struct.pack('>I', len(msg)) + msg
    sock.sendall(msg)

def recv_msg(sock):
    """Nhận một thông điệp có tiền tố là độ dài."""
    raw_msglen = recvall(sock, 4)
    if not raw_msglen:
        return None
    msglen = struct.unpack('>I', raw_msglen)[0]
    return recvall(sock, msglen)

def recvall(sock, n):
    """Nhận chính xác n byte từ socket."""
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data

# --- Lớp Server chính ---
class RemoteDesktopServer:
    def __init__(self, host='192.168.1.7', port=9999):
        self.host = host
        self.port = port
        self.server_socket = None
        self.client_conn = None
        self.is_running = False
        self.input_handler = RemoteInputHandler()
        self.ui = None
        self.capture_thread = None
        self.receive_thread = None

    def start(self):
        """Khởi động server, lắng nghe kết nối."""
        self.is_running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)
        self.update_ui_status(f"Server đang lắng nghe trên {self.host}:{self.port}")

        # Chạy vòng lặp chấp nhận kết nối trong một thread riêng để không block UI
        threading.Thread(target=self.accept_connections, daemon=True).start()

    def accept_connections(self):
        """Vòng lặp chấp nhận kết nối từ client."""
        while self.is_running:
            try:
                self.client_conn, addr = self.server_socket.accept()
                self.update_ui_status(f"Đã kết nối bởi {addr}")
                # Bắt đầu các thread để giao tiếp với client
                self.capture_thread = threading.Thread(target=self.stream_screen, daemon=True)
                self.receive_thread = threading.Thread(target=self.receive_inputs, daemon=True)
                self.capture_thread.start()
                self.receive_thread.start()
            except OSError:
                # Socket đã bị đóng
                break
            except Exception as e:
                self.update_ui_status(f"Lỗi chấp nhận kết nối: {e}")
                break
        self.update_ui_status("Vòng lặp chấp nhận đã dừng.")

    def stop(self):
        """Dừng server và đóng các kết nối."""
        self.is_running = False
        if self.client_conn:
            try:
                self.client_conn.close()
            except Exception as e:
                print(f"Lỗi khi đóng client socket: {e}")
        if self.server_socket:
            try:
                # Đóng socket để ngắt vòng lặp accept()
                self.server_socket.close()
            except Exception as e:
                print(f"Lỗi khi đóng server socket: {e}")
        self.update_ui_status("Server đã dừng.")

    def stream_screen(self):
        """Chụp màn hình và gửi các khung hình đến client."""
        with mss() as sct:
            monitor = sct.monitors[1]
            while self.is_running and self.client_conn:
                try:
                    start_time = time.time()

                    # Chụp màn hình
                    img = sct.grab(monitor)
                    img_pil = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")

                    # Nén ảnh thành JPEG
                    # Thay đổi chất lượng (quality) để cân bằng giữa độ nét và băng thông
                    img_np = np.array(img_pil)
                    frame = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                    _, encoded_frame = cv2.imencode(".jpg", frame, encode_param)

                    # Gửi khung hình đã nén
                    send_msg(self.client_conn, encoded_frame.tobytes())

                    # Giới hạn tốc độ khung hình (FPS)
                    elapsed = time.time() - start_time
                    sleep_time = (1/30) - elapsed # Mục tiêu 30 FPS
                    if sleep_time > 0:
                        time.sleep(sleep_time)

                except (ConnectionResetError, BrokenPipeError):
                    self.update_ui_status("Client đã ngắt kết nối.")
                    break
                except Exception as e:
                    self.update_ui_status(f"Lỗi khi stream: {e}")
                    traceback.print_exc()
                    break
        self.client_conn.close()

    def receive_inputs(self):
        """Nhận và xử lý các lệnh điều khiển từ client."""
        while self.is_running and self.client_conn:
            try:
                data = recv_msg(self.client_conn)
                if data is None:
                    self.update_ui_status("Client đã ngắt kết nối (input).")
                    break
                # Xử lý sự kiện trong một thread riêng để không làm chậm việc nhận
                self.input_handler.process_event(data.decode('utf-8'))
            except (ConnectionResetError, BrokenPipeError):
                break
            except Exception as e:
                self.update_ui_status(f"Lỗi khi nhận input: {e}")
                break

    def create_ui(self):
        """Tạo giao diện người dùng Tkinter cho server."""
        self.ui = tk.Tk()
        self.ui.title("Remote Desktop Server")
        self.ui.geometry("400x150")

        main_frame = ttk.Frame(self.ui, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        self.status_label = ttk.Label(main_frame, text="Server chưa chạy", wraplength=380)
        self.status_label.pack(pady=10)

        start_button = ttk.Button(main_frame, text="Bắt đầu Server", command=self.start)
        start_button.pack(pady=5)

        stop_button = ttk.Button(main_frame, text="Dừng Server", command=self.on_closing)
        stop_button.pack(pady=5)

        self.ui.protocol("WM_DELETE_WINDOW", self.on_closing)
        return self.ui

    def update_ui_status(self, message):
        """Cập nhật nhãn trạng thái trên UI."""
        print(message) # In ra console để debug
        if self.ui and self.status_label:
            self.ui.after(0, lambda: self.status_label.config(text=message))

    def on_closing(self):
        """Xử lý sự kiện đóng cửa sổ UI."""
        self.stop()
        if self.ui:
            self.ui.destroy()

if __name__ == '__main__':
    server = RemoteDesktopServer()
    app_ui = server.create_ui()
    app_ui.mainloop()
