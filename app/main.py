"""
app/main.py - Entrypoint chính thức của VQPVEO3PRO (Phase 1).

Theo đúng kiến trúc mới: Khởi tạo logger, kiểm tra dependency, và bật PySide6 Shell.
"""

import sys
import os

# Đảm bảo đường dẫn gốc được đưa vào sys.path để import
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 1. Quản lý dependency (Cài thiếu thư viện, kiểm tra FFmpeg)
from utils.dependency_manager import verify_all
verify_all()

# 2. Khởi tạo Logger
from utils.logger import app_logger

# 3. Khởi tạo UI
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    app_logger.info("Đang khởi tạo giao diện PySide6 (Phase 1 Architecture)...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        
    app.setApplicationName("VQPVEO3PRO")
    app.setOrganizationName("VQP Studio")
    
    window = MainWindow()
    window.show()
    
    app_logger.info("Ứng dụng đã khởi động thành công.")
    
    try:
        exit_code = app.exec()
    finally:
        app_logger.info("Đã đóng ứng dụng an toàn.")
        
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
