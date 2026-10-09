"""
chrome/chrome_manager.py - Khởi chạy trình duyệt Chrome với profile và extension.
"""
import os
import subprocess
import winreg
from utils.logger import app_logger
from chrome.profile_manager import ChromeProfileManager

class ChromeManager:
    @staticmethod
    def get_chrome_executable():
        """Tìm đường dẫn file chrome.exe qua Registry."""
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
            path, _ = winreg.QueryValueEx(key, "")
            winreg.CloseKey(key)
            return path
        except WindowsError:
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
                path, _ = winreg.QueryValueEx(key, "")
                winreg.CloseKey(key)
                return path
            except WindowsError:
                # Fallback paths
                paths = [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
                ]
                for p in paths:
                    if os.path.exists(p): return p
        return None

    @staticmethod
    def launch_chrome(profile_dir: str, hidden=True):
        """Mở Chrome với profile chỉ định và load Extension Local Bridge.
        
        Args:
            profile_dir: Tên thư mục profile Chrome (vd: "Profile 1")
            hidden: Nếu True, Chrome sẽ chạy ẩn (off-screen + minimized)
        """
        chrome_exe = ChromeManager.get_chrome_executable()
        if not chrome_exe:
            raise FileNotFoundError("Không tìm thấy trình duyệt Chrome trên máy tính.")
            
        user_data_dir = ChromeProfileManager.get_chrome_user_data_dir()
        
        # Đường dẫn tuyệt đối tới extension trong project
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        ext_path = os.path.join(project_root, "chrome_extension")
        
        args = [
            chrome_exe,
            f'--user-data-dir={user_data_dir}',
            f'--profile-directory={profile_dir}',
            f'--load-extension={ext_path}',
            '--remote-allow-origins=*',
            'https://flow.google.com/'
        ]
        
        # Chạy ẩn bằng cách đẩy ra ngoài màn hình và minimize
        # (Chế độ headless=new có thể làm ngắt kết nối WebSocket của Extension)
        if hidden:
            args.insert(-1, '--window-position=-32000,-32000')
            args.insert(-1, '--window-size=1280,800')
            args.insert(-1, '--start-minimized')
        
        app_logger.info(f"Đang khởi chạy Chrome {'(ẩn)' if hidden else ''} với Profile: {profile_dir}")
        
        # Dùng CREATE_NO_WINDOW để không hiện cmd window
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0 if hidden else 1  # 0 = SW_HIDE, 1 = SW_NORMAL
        
        subprocess.Popen(args, startupinfo=startupinfo)
