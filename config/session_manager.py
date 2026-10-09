"""
config/session_manager.py - Quản lý trạng thái phiên làm việc (Session) của ứng dụng.
Lưu lại giao diện và tiến trình để phục hồi khi mở lại.
"""

import json
import os
from pathlib import Path
from utils.json_store import write_json_atomic
from utils.logger import app_logger

SESSION_FILE = Path(__file__).resolve().parent / "session.json"

def save_session(data: dict):
    """Lưu dữ liệu phiên làm việc vào JSON."""
    try:
        write_json_atomic(SESSION_FILE, data)
        app_logger.info("Đã lưu Session làm việc thành công.")
    except Exception as e:
        app_logger.error(f"Lỗi khi lưu Session: {str(e)}")

def load_session() -> dict:
    """Tải dữ liệu phiên làm việc nếu có."""
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception as e:
            app_logger.error(f"Lỗi khi đọc Session: {str(e)}")
            return {}
    return {}

def clear_session():
    """Xóa file session hiện tại (Bắt đầu phiên mới)."""
    if os.path.exists(SESSION_FILE):
        try:
            os.remove(SESSION_FILE)
            app_logger.info("Đã xóa Session cũ.")
        except Exception as e:
            pass
