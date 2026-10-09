"""
chrome/flow_controller.py - Trình quản lý điều phối Job gửi tới Chrome.
"""
from PySide6.QtCore import QObject, Signal
import time
from utils.logger import app_logger

class FlowController(QObject):
    """
    Nhận lệnh từ Visual Provider và gửi qua BridgeServerThread.
    """
    job_completed_signal = Signal(str, dict) # seg_id, result_data
    job_failed_signal = Signal(str, str) # seg_id, error_message

    def __init__(self, bridge_thread):
        super().__init__()
        self.bridge_thread = bridge_thread
        self.bridge_thread.message_received_signal.connect(self._on_bridge_message)

    def request_generation(self, seg_id: str, prompt: str, ratio: str = None, model: str = None, num_images: str = None):
        """Yêu cầu Chrome sinh ảnh."""
        if not getattr(self.bridge_thread, 'clients', None):
            self.job_failed_signal.emit(seg_id, "Chrome chưa kết nối.")
            return

        payload = {
            "type": "GENERATE_IMAGE",
            "seg_id": seg_id,
            "prompt": prompt
        }
        if ratio and ratio != "Mặc định": payload["ratio"] = ratio
        if model and model != "Mặc định": payload["model"] = model
        if num_images and num_images != "Mặc định": payload["num_images"] = num_images
        
        app_logger.info(f"Gửi yêu cầu sinh ảnh lên Chrome cho phân đoạn {seg_id} với options: {payload}")
        self.bridge_thread.send_message(payload)

    def _on_bridge_message(self, data: dict):
        msg_type = data.get('type')
        if msg_type == 'GENERATION_COMPLETED':
            seg_id = data.get('seg_id')
            app_logger.info(f"Đã nhận phản hồi thành công từ Chrome cho {seg_id}")
            self.job_completed_signal.emit(seg_id, data)
        elif msg_type == 'GENERATION_ERROR':
            seg_id = data.get('seg_id')
            err = data.get('error', 'Unknown error')
            app_logger.error(f"Lỗi từ Chrome khi sinh ảnh {seg_id}: {err}")
            self.job_failed_signal.emit(seg_id, err)
