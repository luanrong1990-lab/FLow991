"""
config/settings.py - Cấu hình hệ thống (System Settings) cho VQPVEO3PRO.

Lưu trữ các cấu hình tĩnh, biến môi trường và thiết lập mặc định của hệ thống.
"""

import os
from pathlib import Path

class Settings:
    # Thư mục gốc của project
    BASE_DIR = Path(__file__).resolve().parent.parent
    
    # Các thư mục hệ thống
    LOGS_DIR = BASE_DIR / "logs"
    PROJECTS_DIR = BASE_DIR / "projects"
    
    # --- Cấu hình chung (General) ---
    APP_NAME = "VQPVEO3PRO"
    APP_VERSION = "2.0.0 (Phase 1)"
    
    # --- Database ---
    DATABASE_PATH = BASE_DIR / "project.db"
    
    # --- API Keys ---
    # Trong môi trường thực tế, không nên hardcode key ở đây.
    # Nên load từ biến môi trường hoặc từ file cấu hình của người dùng.
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    
    # --- Lựa chọn AI Mặc định ---
    DEFAULT_AI_PROVIDER = "Gemini"
    
settings = Settings()

# Đảm bảo các thư mục tồn tại
settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
settings.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
