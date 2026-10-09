"""
utils/dependency_manager.py - Trình Quản lý Gói (Dependency Manager).

Chức năng:
1. Kiểm tra sự tồn tại của các thư viện Python bắt buộc.
2. Kiểm tra FFmpeg có được cài đặt và thêm vào PATH chưa.
3. Tự động cài đặt (pip install) nếu thiếu thư viện Python.
"""

import sys
import subprocess
import importlib.util
from utils.logger import app_logger

# Danh sách các thư viện Python bắt buộc cho Phase 1 & 2
REQUIRED_PACKAGES = [
    ("PySide6", "PySide6"),
    ("requests", "requests"),
    ("PIL", "Pillow"),
    # Có thể thêm pydantic, faster-whisper, v.v. vào các Phase sau
]

def check_and_install_dependencies():
    """
    Kiểm tra và tự động cài đặt các dependency bị thiếu.
    """
    app_logger.info("Đang kiểm tra các dependency cần thiết...")
    
    missing_packages = []
    
    for module_name, package_name in REQUIRED_PACKAGES:
        # Sử dụng importlib để kiểm tra xem module có tồn tại không
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            missing_packages.append(package_name)
            
    if missing_packages:
        app_logger.warning(f"Phát hiện thiếu các thư viện: {', '.join(missing_packages)}")
        app_logger.info("Bắt đầu tự động cài đặt...")
        
        for package in missing_packages:
            app_logger.info(f"Đang cài đặt {package}...")
            try:
                # Chạy pip install qua subprocess
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", package],
                    stdout=subprocess.DEVNULL, # Ẩn bớt output chi tiết của pip
                    stderr=subprocess.STDOUT
                )
                app_logger.info(f"Đã cài đặt thành công: {package}")
            except subprocess.CalledProcessError as e:
                app_logger.error(f"Lỗi khi cài đặt {package}: {e}")
                app_logger.error("Vui lòng tự cài đặt bằng lệnh: pip install " + package)
                # Dừng app nếu cài đặt thất bại
                sys.exit(1)
                
    app_logger.info("Tất cả thư viện Python đã được đáp ứng.")
    
def check_ffmpeg():
    """
    Kiểm tra xem FFmpeg đã có sẵn trong hệ thống (PATH) chưa.
    """
    app_logger.info("Đang kiểm tra FFmpeg...")
    try:
        # Gọi lệnh ffmpeg -version
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            app_logger.info(f"Tìm thấy FFmpeg: {version_line}")
            return True
        return False
    except FileNotFoundError:
        app_logger.error("KHÔNG TÌM THẤY FFmpeg!")
        app_logger.error("FFmpeg là bắt buộc để xử lý video và audio.")
        app_logger.error("Vui lòng tải FFmpeg và thêm vào biến môi trường PATH.")
        # Tạm thời chưa ngắt app ở Phase 1 vì chưa đụng tới video render, nhưng sẽ cảnh báo.
        return False

def verify_all():
    """Thực thi toàn bộ quy trình kiểm tra dependency trước khi khởi động."""
    app_logger.info("Khởi động Dependency Manager...")
    check_and_install_dependencies()
    check_ffmpeg()
    app_logger.info("Hoàn tất quá trình kiểm tra môi trường.")
