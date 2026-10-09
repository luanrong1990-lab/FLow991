"""
ai/base.py - Lớp trừu tượng cho các AI Providers.

Định nghĩa interface bắt buộc cho mọi Provider để hệ thống dễ dàng mở rộng 
(Gemini, OpenAI, OpenRouter...) theo đúng chuẩn Phase 2.
"""

from abc import ABC, abstractmethod

class AIProvider(ABC):
    @abstractmethod
    def generate_script(
        self, 
        topic: str, 
        audience: str = "Tất cả", 
        style: str = "Tự nhiên",
        language: str = "Tiếng Việt",
        duration: str = "1 - 3 phút"
    ) -> str:
        """
        Nhận vào một chủ đề (hoặc nội dung bài báo) và các thông số cấu hình.
        Trả về kịch bản lời thoại thuần túy (Voiceover) cùng Metadata SEO dạng JSON.
        """
        pass

    @abstractmethod
    def generate(self, system_instruction: str, prompt: str) -> str:
        """
        Gửi prompt chung tới AI để lấy dữ liệu (ví dụ: Visual Prompts).
        """
        pass
