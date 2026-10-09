"""
chrome/bridge_server.py - Local WebSocket Bridge
Xử lý giao tiếp hai chiều giữa Python Desktop App và Chrome Extension.
"""
import asyncio
import json
import websockets
from PySide6.QtCore import QThread, Signal
from utils.logger import app_logger

class BridgeServerThread(QThread):
    connected_signal = Signal(bool)
    message_received_signal = Signal(dict)

    def __init__(self, host="127.0.0.1", port=8765):
        super().__init__()
        self.host = host
        self.port = port
        self.loop = None
        self.server = None
        self.clients = []
        self.task_queue = []

    async def handle_client(self, websocket):
        app_logger.info("Một Chrome Extension đã kết nối vào Local Bridge.")
        setattr(websocket, 'is_busy', False)
        if websocket not in self.clients:
            self.clients.append(websocket)
        self.connected_signal.emit(True)
        self._try_dispatch() # Kích hoạt job queue khi có client mới kết nối
        try:
            async for message in websocket:
                data = json.loads(message)
                self.message_received_signal.emit(data)
                
                msg_type = data.get("type")
                if msg_type in ["GENERATION_COMPLETED", "GENERATION_ERROR"]:
                    setattr(websocket, 'is_busy', False)
                    self._try_dispatch() # Phân công việc tiếp theo nếu có
                
                # Phản hồi lại PING
                if msg_type == "HANDSHAKE":
                    app_logger.info(f"Handshake từ: {data.get('client')} (v{data.get('version')})")
                elif msg_type == "SAVE_CONFIG":
                    self._save_config(data.get("config"))
                elif msg_type == "GET_CONFIG":
                    cfg = self._load_config()
                    await websocket.send(json.dumps({"type": "LOAD_CONFIG", "config": cfg}))
        except Exception as e:
            app_logger.warning(f"Mất kết nối với Chrome Extension: {e}")
        finally:
            self.clients.remove(websocket)
            if not self.clients:
                self.connected_signal.emit(False)

    def _get_config_path(self):
        import os
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        return os.path.join(project_root, "temp_workspace", "vq_global_config.json")

    def _save_config(self, config_data):
        import json, os
        path = self._get_config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        app_logger.info("Đã đồng bộ hóa Cấu hình Extension toàn cầu.")

    def _load_config(self):
        import json, os
        path = self._get_config_path()
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def run(self):
        asyncio.run(self.main())

    async def main(self):
        self.loop = asyncio.get_running_loop()
        app_logger.info(f"Khởi động Local Bridge tại ws://{self.host}:{self.port}")
        
        try:
            # Dùng websockets.serve hỗ trợ phiên bản mới
            async with websockets.serve(self.handle_client, self.host, self.port) as server:
                self.server = server
                await asyncio.Future()  # Run forever
        except asyncio.CancelledError:
            pass

    def stop(self):
        if self.loop and self.loop.is_running():
            if hasattr(self, 'server') and self.server:
                self.server.close()
            self.loop.call_soon_threadsafe(self.loop.stop)
            
    def send_message(self, message: dict):
        """Thêm Job vào hàng đợi và điều phối"""
        if not self.loop:
            app_logger.warning("Vòng lặp chưa khởi tạo.")
            return
            
        self.task_queue.append(message)
        self._try_dispatch()

    def _try_dispatch(self):
        """Điều phối các Job đang chờ cho những Profile rảnh rỗi"""
        if not self.loop: return
        
        async def _dispatch_async():
            idle_clients = [c for c in self.clients if not getattr(c, 'is_busy', False)]
            for client in idle_clients:
                if not self.task_queue:
                    break # Hết việc
                
                msg = self.task_queue.pop(0)
                setattr(client, 'is_busy', True)
                
                try:
                    await client.send(json.dumps(msg))
                    app_logger.info("Đã giao Job cho 1 Profile rảnh rỗi")
                except Exception as e:
                    app_logger.error(f"Lỗi khi gửi Job tới Profile: {e}")
                    setattr(client, 'is_busy', False)
                    self.task_queue.insert(0, msg) # Trả lại vào hàng đợi
                    if client in self.clients:
                        self.clients.remove(client)
                        
        asyncio.run_coroutine_threadsafe(_dispatch_async(), self.loop)
