"""
config/config_manager.py - Quản lý lưu trữ cấu hình người dùng (User Settings).

Đọc và lưu các thiết lập, API Key từ file JSON để đảm bảo an toàn và tính bền vững.
Hỗ trợ lấy ngẫu nhiên API Key từ danh sách.
"""

import json
import random
from pathlib import Path
from utils.json_store import write_json_atomic

SETTINGS_FILE = Path(__file__).resolve().parent / "user_settings.json"

def load_settings():
    """Tải cấu hình từ file JSON. Trả về dict."""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}

def save_settings(data):
    """Cập nhật và lưu cấu hình vào file JSON."""
    current = load_settings()
    current.update(data)
    write_json_atomic(SETTINGS_FILE, current)

def get_random_api_key(provider="Gemini"):
    """
    Đọc cấu hình API keys (cách nhau bởi dấu phẩy) của provider.
    Trả về ngẫu nhiên 1 key hợp lệ để tránh bị rate limit (sử dụng dạng random thay vì round-robin).
    """
    settings = load_settings()
    # Key lưu trong JSON dạng: "Gemini (Google)_API_KEYS"
    keys_str = settings.get(f"{provider}_API_KEYS", "")
    
    # Tách các key bằng dấu phẩy và loại bỏ khoảng trắng dư thừa
    keys = [k.strip() for k in keys_str.split(",") if k.strip()]
    
    if keys:
        # Chọn ngẫu nhiên 1 key trong danh sách
        return random.choice(keys)
    return ""
