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

# --- Chức năng Mạng (giống hệt server) ---
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

# --- Lớp Client chính ---
class RemoteDesktopClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Remote Desktop Client")
        self.root.geometry("1024x768")

        self.sock = None
        self.is_connected = False
        self.frame_queue = queue.Queue(maxsize=30) # Hàng đợi để chứa các khung hình
        self.input_listeners = []

        self.create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        # Frame điều khiển
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.pack(fill=tk.X)

        ttk.Label(control_frame, text="Server IP:").pack(side=tk.LEFT, padx=5)
        self.ip_entry = ttk.Entry(control_frame, width=20)
        self.ip_entry.insert(0, "127.0.0.1")
        self.ip_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(control_frame, text="Port:").pack(side=tk.LEFT, padx=5)
        self.port_entry = ttk.Entry(control_frame, width=10)
        self.port_entry.insert(0, "9999")
        self.port_entry.pack(side=tk.LEFT, padx=5)

        self.connect_button = ttk.Button(control_frame, text="Kết nối", command=self.toggle_connection)
        self.connect_button.pack(side=tk.LEFT, padx=10)

        # Label hiển thị màn hình
        self.screen_label = ttk.Label(self.root, background="black")
        self.screen_label.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        # Gán sự kiện cho label màn hình
        self.screen_label.bind("<Button>", self.on_mouse_click)
        self.screen_label.bind("<ButtonRelease>", self.on_mouse_click)
        self.screen_label.bind("<Motion>", self.on_mouse_move)
        # Tkinter không có sự kiện scroll chuẩn cho mọi nền tảng, dùng pynput tốt hơn
        # UI sẽ nhận focus để bắt sự kiện bàn phím
        self.screen_label.bind("<FocusIn>", lambda e: self.status_var.set("Focus In. Keyboard active."))
        self.screen_label.bind("<FocusOut>", lambda e: self.status_var.set("Focus Out. Keyboard inactive."))
        
        # Status Bar
        self.status_var = tk.StringVar(value="Sẵn sàng để kết nối.")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def toggle_connection(self):
        if self.is_connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        host = self.ip_entry.get()
        port_str = self.port_entry.get()
        if not host or not port_str:
            messagebox.showerror("Lỗi", "Vui lòng nhập IP và Port.")
            return

        try:
            port = int(port_str)
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, port))
            self.is_connected = True
            self.status_var.set(f"Đã kết nối tới {host}:{port}")
            self.connect_button.config(text="Ngắt kết nối")
            
            # Bắt đầu thread nhận khung hình
            threading.Thread(target=self.receive_frames, daemon=True).start()
            
            # Bắt đầu xử lý hàng đợi khung hình trong UI thread
            self.process_frame_queue()
            
            # Bắt đầu lắng nghe sự kiện input
            self.start_input_listeners()
            self.screen_label.focus_set()

        except Exception as e:
            messagebox.showerror("Lỗi kết nối", str(e))
            import traceback
            traceback.print_exc()
            self.is_connected = False
            self.sock = None

    def disconnect(self):
        self.is_connected = False
        self.connect_button.config(text="Kết nối")
        self.status_var.set("Đã ngắt kết nối.")
        self.stop_input_listeners()
        if self.sock:
            self.sock.close()
            self.sock = None
        # Xóa hình ảnh cuối cùng
        self.screen_label.config(image='')
        self.screen_label.imgtk = None
        # Dọn dẹp hàng đợi
        while not self.frame_queue.empty():
            self.frame_queue.get()

    def receive_frames(self):
        """Nhận dữ liệu khung hình từ server và đưa vào hàng đợi."""
        while self.is_connected:
            try:
                frame_data = recv_msg(self.sock)
                if frame_data is None:
                    # Server đã đóng kết nối
                    break
                if not self.frame_queue.full():
                    self.frame_queue.put(frame_data)
            except (ConnectionResetError, ConnectionAbortedError):
                break
            except Exception as e:
                print(f"Lỗi khi nhận khung hình: {e}")
                break
        
        # Nếu vòng lặp kết thúc, nghĩa là kết nối đã mất
        # Dùng `after` để gọi disconnect trên thread chính của UI
        self.root.after(0, self.disconnect)
        
    def process_frame_queue(self):
        """Lấy khung hình từ hàng đợi và cập nhật UI."""
        try:
            frame_data = self.frame_queue.get_nowait()
            
            # Giải mã frame
            frame_np = np.frombuffer(frame_data, dtype=np.uint8)
            frame = cv2.imdecode(frame_np, cv2.IMREAD_COLOR)

            if frame is not None:
                self.update_screen(frame)

        except queue.Empty:
            pass # Không có frame mới, không làm gì cả
        except Exception as e:
            print(f"Lỗi khi xử lý frame: {e}")
        
        if self.is_connected:
            self.root.after(15, self.process_frame_queue) # Lặp lại sau ~15ms

    def update_screen(self, frame):
        """Cập nhật label với khung hình mới."""
        label_w = self.screen_label.winfo_width()
        label_h = self.screen_label.winfo_height()
        
        # Chuyển đổi màu từ BGR (OpenCV) sang RGB (PIL)
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        
        # Thay đổi kích thước ảnh để vừa với cửa sổ mà vẫn giữ tỷ lệ
        img.thumbnail((label_w, label_h), Image.Resampling.LANCZOS)
        
        img_tk = ImageTk.PhotoImage(image=img)
        self.screen_label.imgtk = img_tk
        self.screen_label.config(image=img_tk)

    def send_event(self, event_data):
        """Gửi dữ liệu sự kiện đến server."""
        if self.is_connected and self.sock:
            try:
                json_data = json.dumps(event_data)
                send_msg(self.sock, json_data.encode('utf-8'))
            except (ConnectionResetError, BrokenPipeError):
                self.root.after(0, self.disconnect)
            except Exception as e:
                print(f"Không thể gửi sự kiện: {e}")
    
    # --- Xử lý Input với Pynput ---
    
    def start_input_listeners(self):
        """Bắt đầu các listener của Pynput."""
        # Dùng pynput thay vì bind của Tkinter để bắt sự kiện toàn cục hơn
        # và xử lý các phím đặc biệt tốt hơn.
        mouse_listener = mouse.Listener(
            on_click=self.on_pynput_press,
            on_scroll=self.on_pynput_scroll
        )
        kbd_listener = keyboard.Listener(
            on_press=self.on_pynput_press,
            on_release=self.on_pynput_release
        )
        mouse_listener.start()
        kbd_listener.start()
        self.input_listeners.extend([mouse_listener, kbd_listener])
    
    def stop_input_listeners(self):
        for listener in self.input_listeners:
            listener.stop()
        self.input_listeners.clear()

    def get_relative_coords(self, abs_x, abs_y):
        """Chuyển đổi tọa độ tuyệt đối của màn hình thành tọa độ tương đối trong label."""
        # Tọa độ gốc của label so với màn hình
        win_x = self.screen_label.winfo_rootx()
        win_y = self.screen_label.winfo_rooty()
        # Kích thước của label
        win_w = self.screen_label.winfo_width()
        win_h = self.screen_label.winfo_height()

        if win_w == 0 or win_h == 0: return None

        # Tính tọa độ tương đối (0.0 to 1.0)
        rel_x = (abs_x - win_x) / win_w
        rel_y = (abs_y - win_y) / win_h
        
        # Chỉ gửi nếu con trỏ nằm trong label
        if 0 <= rel_x <= 1 and 0 <= rel_y <= 1:
            return rel_x, rel_y
        return None

    def on_mouse_move(self, event):
        """Xử lý di chuyển chuột trong label (chỉ dùng để gửi tọa độ)."""
        # Event của tkinter đã cung cấp tọa độ tương đối với widget
        win_w = self.screen_label.winfo_width()
        win_h = self.screen_label.winfo_height()
        if win_w > 1 and win_h > 1:
            rel_x = event.x / win_w
            rel_y = event.y / win_h
            self.send_event({'type': 'mouse', 'action': 'move', 'x': rel_x, 'y': rel_y})

    def on_mouse_click(self, event):
        """Chuyển tiếp sự kiện click chuột (dùng bind của Tkinter)."""
        # Lấy focus khi click
        self.screen_label.focus_set()
        
        # Event type là "ButtonPress" hoặc "ButtonRelease"
        pressed = event.type == tk.EventType.ButtonPress
        
        # Xác định nút chuột
        button_map = {1: 'left', 2: 'middle', 3: 'right'}
        button_name = button_map.get(event.num, 'unknown')

        win_w = self.screen_label.winfo_width()
        win_h = self.screen_label.winfo_height()
        if win_w > 1 and win_h > 1:
            rel_x = event.x / win_w
            rel_y = event.y / win_h
            self.send_event({
                'type': 'mouse', 
                'action': 'click', 
                'x': rel_x, 
                'y': rel_y, 
                'button': button_name, 
                'pressed': pressed
            })
            
    def on_pynput_scroll(self, x, y, dx, dy):
        """Xử lý cuộn chuột (dùng pynput)."""
        # Chỉ gửi nếu con trỏ nằm trong cửa sổ
        coords = self.get_relative_coords(x, y)
        if coords:
            self.send_event({
                'type': 'mouse',
                'action': 'scroll',
                'x': coords[0],
                'y': coords[1],
                'dx': dx,
                'dy': dy
            })
            
    def on_pynput_press(self, key):
        self.send_keyboard_event(key, 'press')

    def on_pynput_release(self, key):
        self.send_keyboard_event(key, 'release')

    def send_keyboard_event(self, key, action):
        """Gửi sự kiện bàn phím."""
        # Chỉ gửi nếu cửa sổ đang focus
        if self.root.focus_get() is not self.screen_label:
            return

        key_str = ''
        if isinstance(key, keyboard.Key):
            key_str = key.name
        elif isinstance(key, keyboard.KeyCode):
            key_str = key.char
        
        if key_str:
            self.send_event({'type': 'keyboard', 'action': action, 'key': key_str})

    def on_closing(self):
        """Xử lý sự kiện đóng cửa sổ."""
        if self.is_connected:
            self.disconnect()
        self.root.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    client_app = RemoteDesktopClient(root)
    root.mainloop()