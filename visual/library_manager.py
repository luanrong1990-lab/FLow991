"""
visual/library_manager.py - Thư viện lưu trữ Visual Styles và Character Presets.

Lưu trữ persistent để tái sử dụng qua nhiều dự án.
- Style Library: Các phong cách hình ảnh đã phân tích/sử dụng
- Character Library: Các nhân vật mẫu đã tạo, dùng lại cho dự án khác
"""

import json
import os
from pathlib import Path
from datetime import datetime
from utils.logger import app_logger

# Đường dẫn lưu trữ thư viện (cùng cấp config)
LIBRARY_DIR = Path(__file__).resolve().parent.parent / "config"
STYLE_LIBRARY_FILE = LIBRARY_DIR / "style_library.json"
CHARACTER_LIBRARY_FILE = LIBRARY_DIR / "character_library.json"


class StyleLibrary:
    """
    Quản lý thư viện phong cách hình ảnh.
    Lưu trữ các style đã phân tích từ ảnh mẫu hoặc do người dùng nhập.
    Mỗi style gồm: tên mô tả, lần sử dụng cuối, số lần dùng.
    """
    
    # Các style mặc định có sẵn (không xóa được)
    DEFAULT_STYLES = [
        "Photorealistic, cinematic lighting",
        "Cinematic film still, dramatic lighting",
        "Hyperrealistic photography, natural light",
        "Digital art, vibrant colors",
        "Oil painting, classical art style",
        "Watercolor illustration, soft tones",
        "Anime / Manga style",
        "3D rendered, Pixar-like",
        "Comic book illustration",
        "Minimalist, flat design",
        "Dark moody, noir style",
        "Fantasy art, epic lighting",
        "Vintage retro, film grain",
        "Sketch / Pencil drawing",
    ]
    
    def __init__(self):
        self.styles = []  # List of dict: {"text": str, "source": str, "used_count": int, "last_used": str}
        self._load()
    
    def _load(self):
        """Tải thư viện từ file JSON."""
        if STYLE_LIBRARY_FILE.exists():
            try:
                with open(STYLE_LIBRARY_FILE, "r", encoding="utf-8") as f:
                    self.styles = json.load(f)
                app_logger.info(f"Đã tải {len(self.styles)} style từ thư viện.")
            except Exception as e:
                app_logger.warning(f"Lỗi tải style library: {e}")
                self.styles = []
    
    def _save(self):
        """Lưu thư viện vào file JSON."""
        try:
            os.makedirs(LIBRARY_DIR, exist_ok=True)
            with open(STYLE_LIBRARY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.styles, f, ensure_ascii=False, indent=2)
        except Exception as e:
            app_logger.error(f"Lỗi lưu style library: {e}")
    
    def add_style(self, text: str, source: str = "manual"):
        """
        Thêm hoặc cập nhật style trong thư viện.
        source: "manual" | "analyzed" | "used"
        """
        text = text.strip()
        if not text:
            return
        
        # Kiểm tra đã tồn tại chưa
        for s in self.styles:
            if s["text"].lower() == text.lower():
                s["used_count"] = s.get("used_count", 0) + 1
                s["last_used"] = datetime.now().isoformat()
                if source == "analyzed":
                    s["source"] = "analyzed"  # Ưu tiên nguồn analyzed
                self._save()
                return
        
        # Thêm mới
        self.styles.insert(0, {
            "text": text,
            "source": source,
            "used_count": 1,
            "last_used": datetime.now().isoformat()
        })
        self._save()
        app_logger.info(f"Đã thêm style mới vào thư viện: {text}")
    
    def remove_style(self, text: str):
        """Xóa 1 style khỏi thư viện."""
        self.styles = [s for s in self.styles if s["text"].lower() != text.lower()]
        self._save()
    
    def get_all_styles(self) -> list:
        """
        Trả về danh sách tất cả styles: user saved (mới nhất trước) + defaults.
        Không trùng lặp.
        """
        # Style đã lưu (sắp xếp theo lần dùng gần nhất)
        saved = sorted(self.styles, key=lambda x: x.get("last_used", ""), reverse=True)
        saved_texts = [s["text"] for s in saved]
        
        # Thêm defaults (nếu chưa có trong saved)
        all_texts = list(saved_texts)
        for d in self.DEFAULT_STYLES:
            if not any(d.lower() == t.lower() for t in all_texts):
                all_texts.append(d)
        
        return all_texts
    
    def get_saved_styles(self) -> list:
        """Chỉ trả về styles do người dùng lưu (không gồm defaults)."""
        return sorted(self.styles, key=lambda x: x.get("last_used", ""), reverse=True)
    
    def mark_used(self, text: str):
        """Đánh dấu style đã được sử dụng (tăng counter)."""
        self.add_style(text, source="used")


class CharacterLibrary:
    """
    Quản lý thư viện nhân vật mẫu (Character Presets).
    Cho phép lưu nhân vật từ dự án này để tái sử dụng cho dự án khác.
    """
    
    def __init__(self):
        self.presets = []  # List of dict (character data + metadata)
        self._load()
    
    def _load(self):
        """Tải thư viện từ file JSON."""
        if CHARACTER_LIBRARY_FILE.exists():
            try:
                with open(CHARACTER_LIBRARY_FILE, "r", encoding="utf-8") as f:
                    self.presets = json.load(f)
                app_logger.info(f"Đã tải {len(self.presets)} character preset từ thư viện.")
            except Exception as e:
                app_logger.warning(f"Lỗi tải character library: {e}")
                self.presets = []
    
    def _save(self):
        """Lưu thư viện vào file JSON."""
        try:
            os.makedirs(LIBRARY_DIR, exist_ok=True)
            with open(CHARACTER_LIBRARY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.presets, f, ensure_ascii=False, indent=2)
        except Exception as e:
            app_logger.error(f"Lỗi lưu character library: {e}")
    
    def save_character(self, char_data: dict):
        """
        Lưu nhân vật vào thư viện. Nếu trùng tên thì ghi đè.
        char_data: dict chứa các field của Character dataclass.
        """
        name = char_data.get("name", "").strip()
        if not name:
            return
        
        # Xóa nhân vật cùng tên nếu đã tồn tại
        self.presets = [p for p in self.presets if p.get("name", "").lower() != name.lower()]
        
        # Thêm metadata
        char_data["saved_at"] = datetime.now().isoformat()
        self.presets.insert(0, char_data)
        self._save()
        app_logger.info(f"Đã lưu nhân vật '{name}' vào thư viện.")
    
    def save_all_characters(self, characters: list):
        """Lưu tất cả nhân vật từ dự án hiện tại vào thư viện."""
        for char_data in characters:
            self.save_character(dict(char_data))  # Copy dict
    
    def remove_character(self, name: str):
        """Xóa nhân vật khỏi thư viện theo tên."""
        self.presets = [p for p in self.presets if p.get("name", "").lower() != name.lower()]
        self._save()
    
    def get_all_presets(self) -> list:
        """Trả về tất cả character presets (mới nhất trước)."""
        return list(self.presets)
    
    def get_preset_by_name(self, name: str) -> dict:
        """Tìm preset theo tên."""
        for p in self.presets:
            if p.get("name", "").lower() == name.lower():
                return p
        return None
