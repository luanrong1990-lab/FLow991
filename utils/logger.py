"""
utils/logger.py - Hệ thống Ghi log (Logging System) cho VQPVEO3PRO.

Chức năng:
1. Ghi log ra console.
2. Ghi log vào file (logs/application.log) với định dạng chuẩn.
"""

import logging
import sys
from pathlib import Path
from config.settings import settings

def setup_logger(name: str = settings.APP_NAME) -> logging.Logger:
    """
    Cấu hình và khởi tạo logger chính cho ứng dụng.
    Ghi log đồng thời ra màn hình (Console) và file (application.log).
    """
    logger = logging.getLogger(name)
    
    # Nếu logger đã được cấu hình, không cần làm lại (tránh bị log trùng lặp)
    if logger.hasHandlers():
        return logger
        
    logger.setLevel(logging.DEBUG)
    
    # Định dạng chuẩn cho log
    formatter = logging.Formatter(
        '%(asctime)s - [%(levelname)s] - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Ghi log ra Console (Màn hình)
    import io
    console_handler = logging.StreamHandler(io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace'))
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Ghi log ra File
    log_file = settings.LOGS_DIR / "application.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    logger.info("=========================================")
    logger.info(f"Khởi động {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("Logger đã được khởi tạo thành công.")
    
    return logger

# Tạo instance logger mặc định để các module khác có thể import và sử dụng trực tiếp
app_logger = setup_logger()
