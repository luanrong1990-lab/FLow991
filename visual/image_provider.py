"""
visual/image_provider.py - Định nghĩa interface tạo ảnh và MockProvider.
"""

import time
import os
from abc import ABC, abstractmethod
from utils.logger import app_logger

class ImageProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, output_path: str) -> bool:
        """Sinh hình ảnh từ prompt và lưu vào output_path."""
        pass

class MockImageProvider(ImageProvider):
    def generate(self, prompt: str, output_path: str) -> bool:
        app_logger.info(f"MockProvider nhận yêu cầu vẽ ảnh: {prompt}")
        time.sleep(2) # Giả lập độ trễ
        
        # Tạo một ảnh Placeholder bằng PySide6 thay vì PIL để không cần thư viện ngoài
        try:
            from PySide6.QtGui import QImage, QPainter, QColor, QFont
            from PySide6.QtCore import Qt
            
            img = QImage(1280, 720, QImage.Format_RGB32)
            img.fill(QColor(73, 109, 137))
            
            painter = QPainter(img)
            painter.setPen(QColor(255, 255, 0))
            painter.setFont(QFont("Arial", 24))
            
            # Cắt ngắn prompt để vẽ lên ảnh
            display_text = f"Mock Generated:\n{prompt[:100]}..."
            painter.drawText(img.rect(), Qt.AlignCenter | Qt.TextWordWrap, display_text)
            painter.end()
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            img.save(output_path)
            
            app_logger.info(f"MockProvider đã lưu ảnh tại {output_path}")
            return True
        except Exception as e:
            app_logger.error(f"Lỗi khi chạy MockProvider: {e}")
            return False
