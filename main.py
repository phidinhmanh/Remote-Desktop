import socket
from typing import overload
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import pickle
import time
import io
from PIL import Image, ImageTk
import pyautogui
from pynput import mouse, keyboard
import base64
import struct
from datetime import datetime
import os


class KeyboardHandler:
    """Xử lý các sự kiện bàn phím"""

    def __init__(self):
        self.listener = None
        self.callback = None

    def start_capture(self, callback):
        """Bắt đầu capture sự kiện bàn phím"""
        self.callback = callback
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self.listener.start()

    def stop_capture(self):
        """Dừng capture sự kiện bàn phím"""
        if self.listener:
            self.listener.stop()

    def _on_press(self, key):
        """Xử lý sự kiện nhấn phím"""
        if self.callback:
            try:
                key_data = {
                    'type': 'key_press',
                    'key': str(key),
                    'timestamp': time.time()
                }
                self.callback(key_data)
            except Exception as e:
                print(f"Keyboard error: {e}")

    def _on_release(self, key):
        """Xử lý sự kiện thả phím"""
        if self.callback:
            try:
                key_data = {
                    'type': 'key_release',
                    'key': str(key),
                    'timestamp': time.time()
                }
                self.callback(key_data)
            except Exception as e:
                print(f"Keyboard error: {e}")

    def simulate_key(self, key_data):
        """Mô phỏng sự kiện bàn phím"""
        try:
            key_str = key_data['key']
            if key_data['type'] == 'key_press':
                if key_str.startswith("'") and key_str.endswith("'"):
                    # Ký tự thường
                    pyautogui.keyDown(key_str[1:-1])
                else:
                    # Phím đặc biệt
                    key_name = key_str.replace('Key.', '')
                    pyautogui.keyDown(key_name)
            elif key_data['type'] == 'key_release':
                if key_str.startswith("'") and key_str.endswith("'"):
                    pyautogui.keyUp(key_str[1:-1])
                else:
                    key_name = key_str.replace('Key.', '')
                    pyautogui.keyUp(key_name)
        except Exception as e:
            print(f"Key simulation error: {e}")

class MouseHandler:
    """Xử lý các sự kiện chuột"""

    def __init__(self):
        self.listener = None
        self.callback = None

    def start_capture(self, callback):
        """Bắt đầu capture sự kiện chuột"""
        self.callback = callback
        self.listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll
        )
        self.listener.start()

    def stop_capture(self):
        """Dừng capture sự kiện chuột"""
        if self.listener:
            self.listener.stop()

    def _on_move(self, x, y):
        """Xử lý sự kiện di chuyển chuột"""
        if self.callback:
            mouse_data = {
                'type': 'mouse_move',
                'x': x,
                'y': y,
                'timestamp': time.time()
            }
            self.callback(mouse_data)

    def _on_click(self, x, y, button, pressed):
        """Xử lý sự kiện click chuột"""
        if self.callback:
            mouse_data = {
                'type': 'mouse_click',
                'x': x,
                'y': y,
                'button': str(button),
                'pressed': pressed,
                'timestamp': time.time()
            }
            self.callback(mouse_data)

    def _on_scroll(self, x, y, dx, dy):
        """Xử lý sự kiện scroll chuột"""
        if self.callback:
            mouse_data = {
                'type': 'mouse_scroll',
                'x': x,
                'y': y,
                'dx': dx,
                'dy': dy,
                'timestamp': time.time()
            }
            self.callback(mouse_data)

    def simulate_mouse(self, mouse_data):
        """Mô phỏng sự kiện chuột"""
        try:
            if mouse_data['type'] == 'mouse_move':
                pyautogui.moveTo(mouse_data['x'], mouse_data['y'])
            elif mouse_data['type'] == 'mouse_click':
                button_map = {
                    'Button.left': 'left',
                    'Button.right': 'right',
                    'Button.middle': 'middle'
                }
                button = button_map.get(mouse_data['button'], 'left')
                if mouse_data['pressed']:
                    pyautogui.mouseDown(mouse_data['x'], mouse_data['y'], button)
                else:
                    pyautogui.mouseUp(mouse_data['x'], mouse_data['y'], button)
            elif mouse_data['type'] == 'mouse_scroll':
                pyautogui.scroll(mouse_data['dy'])
        except Exception as e:
            print(f"Mouse simulation error: {e}")

class ScreenManager:
    """Quản lý màn hình và capture"""

    def __init__(self):
        self.screen_size = pyautogui.size()
        self.capture_quality = 70

    def capture_screen(self):
        """Capture màn hình"""
        try:
            screenshot = pyautogui.screenshot()
            # Resize để giảm kích thước
            screenshot = screenshot.resize((800, 600), Image.Resampling.LANCZOS)

            # Chuyển đổi thành bytes
            img_buffer = io.BytesIO()
            screenshot.save(img_buffer, format='JPEG', quality=self.capture_quality)
            img_data = img_buffer.getvalue()

            return img_data
        except Exception as e:
            print(f"Screen capture error: {e}")
            return None

    def get_screen_info(self):
        """Lấy thông tin màn hình"""
        return {
            'width': self.screen_size.width,
            'height': self.screen_size.height
        }

class VideoStream:
    """Xử lý video stream"""

    def __init__(self):
        self.frame_rate = 10  # FPS
        self.is_streaming = False
        self.callback = None

    def start_stream(self, callback):
        """Bắt đầu streaming video"""
        self.callback = callback
        self.is_streaming = True
        self.stream_thread = threading.Thread(target=self._stream_loop)
        self.stream_thread.daemon = True
        self.stream_thread.start()

    def stop_stream(self):
        """Dừng streaming video"""
        self.is_streaming = False

    def _stream_loop(self):
        """Vòng lặp streaming"""
        screen_manager = ScreenManager()
        while self.is_streaming:
            try:
                frame_data = screen_manager.capture_screen()
                if frame_data and self.callback:
                    self.callback(frame_data)
                time.sleep(1.0 / self.frame_rate)
            except Exception as e:
                print(f"Stream error: {e}")
                time.sleep(0.1)

class MessageControl:
    """Quản lý và xử lý tin nhắn chat"""

    def __init__(self):
        self.message_history = []
        self.callbacks = []
        self.user_name = "User"

    def set_user_name(self, name):
        """Đặt tên người dùng"""
        self.user_name = name

    def add_message(self, sender, message, timestamp=None):
        """Thêm tin nhắn vào lịch sử"""
        if timestamp is None:
            timestamp = datetime.now()

        msg_data = {
            'sender': sender,
            'message': message,
            'timestamp': timestamp,
            'is_system': sender == 'SYSTEM'
        }

        self.message_history.append(msg_data)

        # Notify all callbacks
        for callback in self.callbacks:
            callback(msg_data)

    def register_callback(self, callback):
        """Đăng ký callback khi có tin nhắn mới"""
        self.callbacks.append(callback)

    def unregister_callback(self, callback):
        """Hủy đăng ký callback"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def get_message_history(self):
        """Lấy lịch sử tin nhắn"""
        return self.message_history.copy()

    def clear_history(self):
        """Xóa lịch sử tin nhắn"""
        self.message_history.clear()

    def format_message(self, msg_data):
        """Format tin nhắn để hiển thị"""
        time_str = msg_data['timestamp'].strftime("%H:%M:%S")
        sender = msg_data['sender']
        message = msg_data['message']

        if msg_data['is_system']:
            return f"[{time_str}] >>> {message}"
        else:
            return f"[{time_str}] {sender}: {message}"

class WindowChat:
    """Cửa sổ chat popup"""
    @overload
    def __init__(self, canvas: tk.Canvas): ...

    @overload
    def __init__(self, parent: tk.Tk, socket_connection, message_control, canvas: tk.Canvas, user_type: str = "Host"): ...

    def __init__(self, *args, **kwargs):
        self.is_open = False
        self.current_image = None

        if len(args) == 1:
             # canvas-only constructor
             self.canvas = args[0]
             return

         # full constructor
        parent, socket_connection, message_control, canvas = args[:4]
        user_type = kwargs.get("user_type", "Host")

        self.parent = parent
        self.socket_connection = socket_connection
        self.message_control = message_control
        self.canvas = canvas
        self.user_type = user_type

        self.window = tk.Toplevel(parent)
        self.window.title(f"Chat - {user_type}")
        self.window.geometry("400x500")
        self.window.resizable(True, True)
        self.window.protocol("WM_DELETE_WINDOW", self.hide_window)

        self.setup_ui()
        self.setup_events()
        self.message_control.register_callback(self.on_new_message)
        self.hide_window()

    def setup_ui(self):
        """Thiết lập giao diện chat"""
        # Main frame
        main_frame = ttk.Frame(self.window, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Chat display area
        chat_frame = ttk.LabelFrame(main_frame, text="Chat Messages", padding="5")
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Chat text area với scrollbar
        self.chat_text = scrolledtext.ScrolledText(
            chat_frame,
            height=20,
            width=50,
            state=tk.DISABLED,
            wrap=tk.WORD,
            font=("Consolas", 9)
        )
        self.chat_text.pack(fill=tk.BOTH, expand=True)

        # Configure text tags for different message types
        self.chat_text.tag_configure("system", foreground="#666666", font=("Consolas", 9, "italic"))
        self.chat_text.tag_configure("own", foreground="#0066CC", font=("Consolas", 9, "bold"))
        self.chat_text.tag_configure("other", foreground="#009900", font=("Consolas", 9))
        self.chat_text.tag_configure("timestamp", foreground="#888888", font=("Consolas", 8))

        # Input frame
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=(0, 5))

        # Message input
        self.message_entry = ttk.Entry(input_frame, font=("Arial", 10))
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # Send button
        self.send_btn = ttk.Button(input_frame, text="Send", command=self.send_message)
        self.send_btn.pack(side=tk.RIGHT)

        # Status frame
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X)

        # Status label
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, font=("Arial", 8))
        status_label.pack(side=tk.LEFT)

        # Online indicator
        self.online_var = tk.StringVar(value="● Offline")
        online_label = ttk.Label(status_frame, textvariable=self.online_var, font=("Arial", 8))
        online_label.pack(side=tk.RIGHT)

        # Clear button
        clear_btn = ttk.Button(status_frame, text="Clear", command=self.clear_chat)
        clear_btn.pack(side=tk.RIGHT, padx=(0, 10))

    def setup_events(self):
        """Thiết lập các sự kiện"""
        # Enter key để gửi tin nhắn
        self.message_entry.bind("<Return>", lambda e: self.send_message())

        # Focus vào entry khi mở cửa sổ
        self.window.bind("<FocusIn>", lambda e: self.message_entry.focus())

        # Escape key để ẩn cửa sổ
        self.window.bind("<Escape>", lambda e: self.hide_window())

    def show_window(self):
        """Hiển thị cửa sổ chat"""
        self.window.deiconify()
        self.window.lift()
        self.window.focus()
        self.message_entry.focus()
        self.is_open = True

        # Cập nhật trạng thái online
        self.update_online_status()

    def hide_window(self):
        """Ẩn cửa sổ chat"""
        self.window.withdraw()
        self.is_open = False

    def toggle_window(self):
        """Chuyển đổi hiển thị/ẩn cửa sổ"""
        if self.is_open:
            self.hide_window()
        else:
            self.show_window()

    def send_message(self):
        """Gửi tin nhắn"""
        message = self.message_entry.get().strip()
        if not message:
            return

        # Xóa nội dung input
        self.message_entry.delete(0, tk.END)

        # Thêm tin nhắn vào lịch sử local
        self.message_control.add_message(self.user_type, message)

        # Gửi qua socket nếu có kết nối
        if self.socket_connection and self.socket_connection.is_connected:
            chat_data = {
                'sender': self.user_type,
                'message': message,
                'timestamp': datetime.now().isoformat()
            }
            self.socket_connection.send_data('chat_message', chat_data)
            self.status_var.set("Message sent")
        else:
            self.status_var.set("No connection")

    def receive_message(self, chat_data):
        """Nhận tin nhắn từ remote"""
        sender = chat_data['sender']
        message = chat_data['message']
        timestamp = datetime.fromisoformat(chat_data['timestamp'])

        # Thêm vào lịch sử
        self.message_control.add_message(sender, message, timestamp)

        # Hiển thị thông báo nếu cửa sổ đang ẩn
        if not self.is_open:
            self.show_notification(sender, message)

    def show_notification(self, sender, message):
        """Hiển thị thông báo tin nhắn mới"""
        # Thay đổi title để báo hiệu có tin nhắn mới
        self.window.title(f"Chat - {self.user_type} (New Message!)")

        # Có thể thêm sound notification hoặc system notification
        self.parent.bell()  # System beep

        # Reset title sau 3 giây
        self.window.after(3000, lambda: self.window.title(f"Chat - {self.user_type}"))

    def on_new_message(self, msg_data):
        """Callback khi có tin nhắn mới"""
        self.display_message(msg_data)

    def display_message(self, msg_data):
        """Hiển thị tin nhắn trong chat area"""
        self.chat_text.config(state=tk.NORMAL)

        formatted_msg = self.message_control.format_message(msg_data)

        # Xác định kiểu tin nhắn
        if msg_data['is_system']:
            tag = "system"
        elif msg_data['sender'] == self.user_type:
            tag = "own"
        else:
            tag = "other"

        # Thêm tin nhắn với tag phù hợp
        self.chat_text.insert(tk.END, formatted_msg + "\n", tag)

        # Scroll xuống cuối
        self.chat_text.see(tk.END)

        self.chat_text.config(state=tk.DISABLED)

    def clear_chat(self):
        """Xóa nội dung chat"""
        result = messagebox.askyesno("Clear Chat", "Are you sure you want to clear all chat messages?")
        if result:
            self.chat_text.config(state=tk.NORMAL)
            self.chat_text.delete(1.0, tk.END)
            self.chat_text.config(state=tk.DISABLED)

            # Xóa lịch sử tin nhắn
            self.message_control.clear_history()

            # Thông báo system
            self.message_control.add_message("SYSTEM", "Chat cleared")

    def update_online_status(self):
        """Cập nhật trạng thái online"""
        if self.socket_connection and self.socket_connection.is_connected:
            self.online_var.set("● Online")
        else:
            self.online_var.set("● Offline")

    def load_message_history(self):
        """Tải lịch sử tin nhắn"""
        history = self.message_control.get_message_history()

        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.delete(1.0, tk.END)

        for msg_data in history:
            self.display_message(msg_data)

        self.chat_text.config(state=tk.DISABLED)

    def destroy(self):
        """Hủy cửa sổ chat"""
        # Hủy đăng ký callback
        self.message_control.unregister_callback(self.on_new_message)

        # Destroy window
        self.window.destroy()
    """Adapter cho việc hiển thị màn hình"""



    def update_screen(self, image_data):
        """Cập nhật hiển thị màn hình"""
        try:
            # Chuyển đổi bytes thành image
            image = Image.open(io.BytesIO(image_data))
            photo = ImageTk.PhotoImage(image)

            # Cập nhật canvas
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=photo)
            self.current_image = photo  # Giữ reference

            # Cập nhật kích thước canvas
            self.canvas.config(scrollregion=self.canvas.bbox("all"))
        except Exception as e:
            print(f"Screen adapter error: {e}")

class SocketConnection:
    """Quản lý kết nối socket"""

    def __init__(self):
        self.socket = None
        self.is_connected = False
        self.message_handlers = {}

    def start_server(self, host='localhost', port=9999):
        """Khởi động server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((host, port))
            self.socket.listen(1)
            print(f"Server started on {host}:{port}")

            # Chấp nhận kết nối
            client_socket, addr = self.socket.accept()
            print(f"Client connected from {addr}")

            self.socket = client_socket
            self.is_connected = True

            # Bắt đầu nhận dữ liệu
            self.receive_thread = threading.Thread(target=self._receive_loop)
            self.receive_thread.daemon = True
            self.receive_thread.start()

            return True
        except Exception as e:
            print(f"Server start error: {e}")
            return False

    def connect_to_server(self, host='localhost', port=9999):
        """Kết nối đến server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            self.is_connected = True
            print(f"Connected to server {host}:{port}")

            # Bắt đầu nhận dữ liệu
            self.receive_thread = threading.Thread(target=self._receive_loop)
            self.receive_thread.daemon = True
            self.receive_thread.start()

            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def send_data(self, data_type, data):
        """Gửi dữ liệu"""
        if not self.is_connected or not self.socket:
            return False

        try:
            message = {
                'type': data_type,
                'data': data,
                'timestamp': time.time()
            }

            # Serialize message
            serialized = pickle.dumps(message)

            # Gửi kích thước trước
            size = len(serialized)
            self.socket.sendall(struct.pack('!I', size))

            # Gửi dữ liệu
            self.socket.sendall(serialized)
            return True
        except Exception as e:
            print(f"Send error: {e}")
            self.is_connected = False
            return False

    def _receive_loop(self):
        """Vòng lặp nhận dữ liệu"""
        while self.is_connected:
            try:
                # Nhận kích thước message
                size_data = self.socket.recv(4)
                if not size_data:
                    break

                size = struct.unpack('!I', size_data)[0]

                # Nhận dữ liệu
                data = b''
                while len(data) < size:
                    chunk = self.socket.recv(min(size - len(data), 4096))
                    if not chunk:
                        break
                    data += chunk

                # Deserialize
                message = pickle.loads(data)

                # Xử lý message
                msg_type = message['type']
                if msg_type in self.message_handlers:
                    self.message_handlers[msg_type](message['data'])

            except Exception as e:
                print(f"Receive error: {e}")
                break

        self.is_connected = False

    def register_handler(self, message_type, handler):
        """Đăng ký handler cho loại message"""
        self.message_handlers[message_type] = handler

    def close(self):
        """Đóng kết nối"""
        self.is_connected = False
        if self.socket:
            self.socket.close()

class HostApp:
    """Ứng dụng Host (máy chủ)"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Remote Desktop - Host")
        self.root.geometry("600x500")

        self.connection = SocketConnection()
        self.keyboard_handler = KeyboardHandler()
        self.mouse_handler = MouseHandler()
        self.video_stream = VideoStream()
        self.message_control = MessageControl()
        self.chat_window = None

        self.is_sharing = False
        self.message_control.set_user_name("Host")
        self.setup_ui()

    def setup_ui(self):
        """Thiết lập giao diện"""
        # Frame chính
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Tiêu đề
        title_label = ttk.Label(main_frame, text="Remote Desktop Host",
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # Thông tin kết nối
        #
        connection_frame = ttk.LabelFrame(main_frame, text="Connection Settings", padding="10")
        connection_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(connection_frame, text="Host:").grid(row=0, column=0, sticky=tk.W)
        self.host_entry = ttk.Entry(connection_frame, width=20)
        self.host_entry.insert(0, "localhost")
        self.host_entry.grid(row=0, column=1, padx=(5, 0))

        ttk.Label(connection_frame, text="Port:").grid(row=1, column=0, sticky=tk.W)
        self.port_entry = ttk.Entry(connection_frame, width=20)
        self.port_entry.insert(0, "9999")
        self.port_entry.grid(row=1, column=1, padx=(5, 0))

        # Nút điều khiển
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=2, column=0, columnspan=2, pady=10)

        self.start_btn = ttk.Button(control_frame, text="Start Sharing",
                                   command=self.start_sharing)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.stop_btn = ttk.Button(control_frame, text="Stop Sharing",
                                  command=self.stop_sharing, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Chat button
        self.chat_btn = ttk.Button(control_frame, text="Open Chat",
                                  command=self.toggle_chat, state=tk.DISABLED)
        self.chat_btn.pack(side=tk.LEFT)

        # Trạng thái
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(main_frame, textvariable=self.status_var)
        status_label.grid(row=3, column=0, columnspan=2, pady=10)

        # Log
        log_frame = ttk.LabelFrame(main_frame, text="Activity Log", padding="10")
        log_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=70)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Cấu hình grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)

    def start_sharing(self):
        """Bắt đầu chia sẻ màn hình"""
        host = self.host_entry.get() or "localhost"
        port = int(self.port_entry.get() or "9999")

        if self.connection.start_server(host, port):
            self.is_sharing = True
            self.status_var.set("Sharing...")
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.chat_btn.config(state=tk.NORMAL)  # Enable chat button khi đã sharing

            # Đăng ký handlers
            self.connection.register_handler('mouse_event', self.handle_mouse_event)
            self.connection.register_handler('key_event', self.handle_key_event)
            self.connection.register_handler('chat_message', self.handle_chat_message)

            # Bắt đầu video stream
            self.video_stream.start_stream(self.send_frame)

            # Thông báo có client kết nối
            self.message_control.add_message("SYSTEM", "Client connected - Screen sharing started")

            # Khởi tạo chat window (chỉ khi đã sharing)
            if not self.chat_window:
                self.chat_window = WindowChat(self.root, self.connection, self.message_control, self.canvas, "Host")

            self.log("Started sharing screen")
        else:
            messagebox.showerror("Error", "Failed to start server")

    def stop_sharing(self):
        """Dừng chia sẻ màn hình"""
        self.is_sharing = False
        self.video_stream.stop_stream()
        self.connection.close()

        self.status_var.set("Ready")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.chat_btn.config(state=tk.DISABLED)
        if self.chat_window:
            self.chat_window.hide_window()

        # Thông báo ngắt kết nối
        if self.chat_window:
            self.message_control.add_message("SYSTEM", "Client disconnected - Screen sharing stopped")

        self.log("Stopped sharing screen")

    def send_frame(self, frame_data):
        """Gửi frame video"""
        if self.is_sharing:
            # Encode frame data as base64
            encoded_frame = base64.b64encode(frame_data).decode('utf-8')
            self.connection.send_data('video_frame', encoded_frame)

    def handle_mouse_event(self, mouse_data):
        """Xử lý sự kiện chuột từ client"""
        mouse_handler = MouseHandler()
        mouse_handler.simulate_mouse(mouse_data)
        self.log(f"Mouse event: {mouse_data['type']}")

    def handle_key_event(self, key_data):
        """Xử lý sự kiện bàn phím từ client"""
        keyboard_handler = KeyboardHandler()
        keyboard_handler.simulate_key(key_data)
        self.log(f"Key event: {key_data['type']}")

    def handle_chat_message(self, chat_data):
        """Xử lý tin nhắn chat từ client"""
        if self.chat_window:
            self.chat_window.receive_message(chat_data)
        self.log(f"Chat message from {chat_data['sender']}: {chat_data['message'][:30]}...")

    def toggle_chat(self):
        """Mở/đóng cửa sổ chat"""
        if not self.chat_window:
            self.chat_window = WindowChat(self.root, self.connection, self.message_control, self.canvas, "Host")
        self.chat_window.toggle_window()

    def log(self, message):
        """Ghi log"""
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_message)
        self.log_text.see(tk.END)

    def run(self):
        """Chạy ứng dụng"""
        self.root.mainloop()

class ClientApp:
    """Ứng dụng Client (máy khách)"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Remote Desktop - Client")
        self.root.geometry("900x700")

        self.connection = SocketConnection()
        self.keyboard_handler = KeyboardHandler()
        self.mouse_handler = MouseHandler()
        self.message_control = MessageControl()
        self.chat_window = None

        self.is_connected = False
        self.is_controlling = False
        self.message_control.set_user_name("Client")
        self.setup_ui()

    def setup_ui(self):
        """Thiết lập giao diện"""
        # Frame chính
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Thanh điều khiển
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # Kết nối
        ttk.Label(control_frame, text="Host:").pack(side=tk.LEFT)
        self.host_entry = ttk.Entry(control_frame, width=15)
        self.host_entry.insert(0, "localhost")
        self.host_entry.pack(side=tk.LEFT, padx=(5, 10))

        ttk.Label(control_frame, text="Port:").pack(side=tk.LEFT)
        self.port_entry = ttk.Entry(control_frame, width=8)
        self.port_entry.insert(0, "9999")
        self.port_entry.pack(side=tk.LEFT, padx=(5, 10))

        self.connect_btn = ttk.Button(control_frame, text="Connect",
                                     command=self.connect_to_host)
        self.connect_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.disconnect_btn = ttk.Button(control_frame, text="Disconnect",
                                        command=self.disconnect_from_host, state=tk.DISABLED)
        self.disconnect_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.control_btn = ttk.Button(control_frame, text="Start Control",
                                     command=self.toggle_control, state=tk.DISABLED)
        self.control_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Chat button
        self.chat_btn = ttk.Button(control_frame, text="Open Chat",
                                  command=self.toggle_chat, state=tk.DISABLED)
        self.chat_btn.pack(side=tk.LEFT)

        # Trạng thái
        self.status_var = tk.StringVar(value="Disconnected")
        status_label = ttk.Label(control_frame, textvariable=self.status_var)
        status_label.pack(side=tk.RIGHT)

        # Frame cho màn hình
        screen_frame = ttk.LabelFrame(main_frame, text="Remote Screen", padding="5")
        screen_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Canvas với scrollbars
        canvas_frame = ttk.Frame(screen_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg='black', width=800, height=600)
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)

        self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))

        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)

        # Screen adapter
        # self.screen_adapter = ScreenAdapter(self.canvas)

        # Bind canvas events
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Button-3>", self.on_canvas_click)
        self.canvas.bind("<Motion>", self.on_canvas_motion)
        self.canvas.bind("<MouseWheel>", self.on_canvas_scroll)
        self.canvas.focus_set()  # For keyboard events
        self.canvas.bind("<KeyPress>", self.on_canvas_key)
        self.canvas.bind("<KeyRelease>", self.on_canvas_key)

        # Cấu hình grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

    def connect_to_host(self):
        """Kết nối đến host"""
        host = self.host_entry.get() or "localhost"
        port = int(self.port_entry.get() or "9999")

        if self.connection.connect_to_server(host, port):
            self.is_connected = True
            self.status_var.set("Connected")
            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
            self.control_btn.config(state=tk.NORMAL)
            self.chat_btn.config(state=tk.NORMAL)  # Enable chat button khi đã kết nối

            # Đăng ký handler cho video frame và chat
            self.connection.register_handler('video_frame', self.handle_video_frame)
            self.connection.register_handler('chat_message', self.handle_chat_message)

            # Khởi tạo chat window (chỉ khi đã kết nối)
            if not self.chat_window:
                self.chat_window = WindowChat(self.root, self.connection, self.message_control, self.canvas, "Client")

            # Thông báo kết nối thành công
            self.message_control.add_message("SYSTEM", "Connected to host successfully")
        else:
            messagebox.showerror("Error", "Failed to connect to host")

    def disconnect_from_host(self):
        """Ngắt kết nối khỏi host"""
        self.is_connected = False
        self.is_controlling = False
        self.connection.close()

        self.status_var.set("Disconnected")
        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.control_btn.config(state=tk.DISABLED, text="Start Control")
        self.chat_btn.config(state=tk.DISABLED)
        if self.chat_window:
            self.chat_window.hide_window()

        # Xóa màn hình
        self.canvas.delete("all")

        # Thông báo ngắt kết nối
        if self.chat_window:
            self.message_control.add_message("SYSTEM", "Disconnected from host")

    def toggle_control(self):
        """Bật/tắt điều khiển"""
        if not self.is_controlling:
            self.is_controlling = True
            self.control_btn.config(text="Stop Control")
            self.status_var.set("Connected - Controlling")
        else:
            self.is_controlling = False
            self.control_btn.config(text="Start Control")
            self.status_var.set("Connected")

    def handle_video_frame(self, frame_data):
        """Xử lý frame video nhận được"""
        try:
            # Decode base64
            image_data = base64.b64decode(frame_data.encode('utf-8'))
            self.screen_adapter.update_screen(image_data)
        except Exception as e:
            print(f"Video frame error: {e}")

    def handle_chat_message(self, chat_data):
        """Xử lý tin nhắn chat từ host"""
        if self.chat_window:
            self.chat_window.receive_message(chat_data)

    def toggle_chat(self):
        """Mở/đóng cửa sổ chat"""
        if not self.chat_window:
            self.chat_window = WindowChat(self.root, self.connection, self.message_control, self.canvas, "Client")
        self.chat_window.toggle_window()

    def on_canvas_click(self, event):
        """Xử lý click trên canvas"""
        if self.is_controlling:
            mouse_data = {
                'type': 'mouse_click',
                'x': event.x,
                'y': event.y,
                'button': 'Button.left' if event.num == 1 else 'Button.right',
                'pressed': True,
                'timestamp': time.time()
            }
            self.connection.send_data('mouse_event', mouse_data)

    def on_canvas_motion(self, event):
        """Xử lý di chuyển chuột trên canvas"""
        if self.is_controlling:
            mouse_data = {
                'type': 'mouse_move',
                'x': event.x,
                'y': event.y,
                'timestamp': time.time()
            }
            self.connection.send_data('mouse_event', mouse_data)

    def on_canvas_scroll(self, event):
        """Xử lý scroll trên canvas"""
        if self.is_controlling:
            mouse_data = {
                'type': 'mouse_scroll',
                'x': event.x,
                'y': event.y,
                'dx': 0,
                'dy': event.delta,
                'timestamp': time.time()
            }
            self.connection.send_data('mouse_event', mouse_data)

    def on_canvas_key(self, event):
        """Xử lý phím trên canvas"""
        if self.is_controlling:
            key_data = {
                'type': 'key_press' if event.type == '2' else 'key_release',
                'key': f"'{event.char}'" if event.char else f"Key.{event.keysym.lower()}",
                'timestamp': time.time()
            }
            self.connection.send_data('key_event', key_data)

    def run(self):
        """Chạy ứng dụng"""
        self.root.mainloop()

def main():
    """Hàm main để chọn chế độ"""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'client':
        app = ClientApp()
    else:
        app = HostApp()

    app.run()

if __name__ == "__main__":
    # Chạy trực tiếp sẽ mở Host app
    # Để chạy Client app, sử dụng: python script.py client
    main()
