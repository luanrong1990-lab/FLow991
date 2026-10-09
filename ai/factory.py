"""
ai/factory.py - Factory để khởi tạo AI Provider phù hợp.
"""

from config.config_manager import load_settings
from ai.base import AIProvider
from ai.gemini_provider import GeminiProvider

def get_current_ai_provider() -> AIProvider:
    """
    Đọc thiết lập DEFAULT_AI_PROVIDER từ config và trả về Instance Provider tương ứng.
    """
    settings = load_settings()
    provider_name = settings.get("DEFAULT_AI_PROVIDER", "Gemini (Google)")
    
    if "Gemini" in provider_name:
        return GeminiProvider()
    
    # Placeholder cho OpenAI, OpenRouter trong các phase sau
    # if "OpenAI" in provider_name:
    #     return OpenAIProvider()
        
    return GeminiProvider() # Fallback
