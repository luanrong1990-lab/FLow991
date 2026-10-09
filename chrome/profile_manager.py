"""
chrome/profile_manager.py - Quản lý Profile của Chrome.
Tự động tìm kiếm thư mục User Data và đọc thông tin các Profile hiện có.
"""
import os
import json
from utils.logger import app_logger

class ChromeProfileManager:
    @staticmethod
    def get_chrome_user_data_dir():
        """Tìm đường dẫn thư mục User Data mặc định của Chrome trên Windows."""
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            return ""
        return os.path.join(local_app_data, "Google", "Chrome", "User Data")

    @staticmethod
    def get_available_profiles():
        """
        Đọc file 'Local State' để lấy danh sách các profile.
        Trả về dictionary map profile_directory -> profile_name
        Ví dụ: {"Default": "Person 1", "Profile 1": "Tài khoản làm việc"}
        """
        user_data_dir = ChromeProfileManager.get_chrome_user_data_dir()
        if not os.path.exists(user_data_dir):
            app_logger.warning("Không tìm thấy Chrome User Data Directory.")
            return {}

        local_state_path = os.path.join(user_data_dir, "Local State")
        profiles = {}
        
        if os.path.exists(local_state_path):
            try:
                with open(local_state_path, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    
                info_cache = state.get("profile", {}).get("info_cache", {})
                for profile_dir, info in info_cache.items():
                    name = info.get("name", profile_dir)
                    profiles[profile_dir] = name
                    
            except Exception as e:
                app_logger.error(f"Lỗi khi đọc Local State Chrome: {e}")
                
        # Fallback nếu không có info_cache
        if not profiles:
            app_logger.info("Dùng fallback tìm các thư mục Profile...")
            for d in os.listdir(user_data_dir):
                if d == "Default" or d.startswith("Profile "):
                    profiles[d] = d
                    
        return profiles
