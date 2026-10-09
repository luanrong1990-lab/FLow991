"""
visual/character_manager.py - Quản lý nhân vật để duy trì tính nhất quán cho image prompts.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any

from ai.gemini_provider import GeminiProvider
from utils.logger import app_logger

@dataclass
class Character:
    id: str
    name: str
    age: str
    gender: str
    face: str
    hair: str
    clothing: str
    body_type: str
    personality: str
    visual_style: str
    custom_tags: List[str] = field(default_factory=list)
    reference_image_path: str = ""
    media_id: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> 'Character':
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            age=data.get('age', ''),
            gender=data.get('gender', ''),
            face=data.get('face', ''),
            hair=data.get('hair', ''),
            clothing=data.get('clothing', ''),
            body_type=data.get('body_type', ''),
            personality=data.get('personality', ''),
            visual_style=data.get('visual_style', ''),
            custom_tags=data.get('custom_tags', []),
            reference_image_path=data.get('reference_image_path', ''),
            media_id=data.get('media_id', '')
        )

class CharacterManager:
    def __init__(self):
        self.characters: Dict[str, Character] = {}
        
    def add_character(self, character: Character) -> None:
        """Thêm một nhân vật mới vào hệ thống quản lý."""
        if character.id in self.characters:
            app_logger.warning(f"Nhân vật với ID {character.id} đã tồn tại. Sẽ bị ghi đè.")
        self.characters[character.id] = character
        app_logger.info(f"Đã thêm nhân vật: {character.name} ({character.id})")
        
    def remove_character(self, character_id: str) -> bool:
        """Xóa nhân vật theo ID."""
        if character_id in self.characters:
            del self.characters[character_id]
            app_logger.info(f"Đã xóa nhân vật có ID: {character_id}")
            return True
        app_logger.warning(f"Không tìm thấy nhân vật có ID: {character_id} để xóa.")
        return False
        
    def update_character(self, character_id: str, **kwargs) -> bool:
        """Cập nhật thông tin nhân vật."""
        if character_id not in self.characters:
            app_logger.warning(f"Không tìm thấy nhân vật có ID: {character_id} để cập nhật.")
            return False
            
        character = self.characters[character_id]
        for key, value in kwargs.items():
            if hasattr(character, key):
                setattr(character, key, value)
                
        app_logger.info(f"Đã cập nhật nhân vật: {character_id}")
        return True
        
    def get_character(self, character_id: str) -> Optional[Character]:
        """Lấy thông tin nhân vật theo ID."""
        return self.characters.get(character_id)
        
    def get_all_characters(self) -> List[Character]:
        """Lấy danh sách tất cả nhân vật."""
        return list(self.characters.values())
        
    def build_character_description(self, character_id: str) -> str:
        """
        Tạo đoạn mô tả tiếng Anh gồm 1 đoạn văn cho 1 nhân vật 
        để dùng làm prompt tạo ảnh.
        Ví dụ: 'A 65-year-old Caucasian man with short silver hair and warm brown eyes...'
        """
        char = self.get_character(character_id)
        if not char:
            return ""
            
        desc = []
        if char.age or char.gender:
            age_str = f"{char.age}" if char.age else ""
            gender_str = f"{char.gender}" if char.gender else "person"
            desc.append(f"A {age_str} {gender_str}".strip())
        
        if char.face:
            desc.append(f"with {char.face}")
            
        if char.hair:
            desc.append(f"and {char.hair}")
            
        if char.clothing:
            desc.append(f"wearing {char.clothing}")
            
        if char.body_type:
            desc.append(f", {char.body_type} build")
            
        if char.personality:
            desc.append(f", {char.personality} expression")
            
        tags_str = ", ".join(char.custom_tags) if char.custom_tags else ""
        
        # Kết hợp các phần lại thành câu
        sentence = " ".join(desc).replace(" ,", ",")
        
        if char.visual_style:
            sentence += f", {char.visual_style} style"
            
        if tags_str:
            sentence += f", {tags_str}"
            
        return sentence.strip()
        
    def build_all_descriptions(self) -> str:
        """Tạo đoạn mô tả chung cho tất cả các nhân vật để nhúng vào prompt."""
        descriptions = []
        for char in self.characters.values():
            char_desc = self.build_character_description(char.id)
            if char_desc:
                descriptions.append(f"[{char.id}]: {char_desc}")
                
        return "\n".join(descriptions)
        
    def save_to_file(self, filepath: str) -> bool:
        """Lưu danh sách nhân vật ra file JSON."""
        try:
            data = {char_id: asdict(char) for char_id, char in self.characters.items()}
            
            # Đảm bảo thư mục tồn tại
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
                
            app_logger.info(f"Đã lưu danh sách nhân vật vào: {filepath}")
            return True
        except Exception as e:
            app_logger.error(f"Lỗi khi lưu danh sách nhân vật: {str(e)}")
            return False
            
    def load_from_file(self, filepath: str) -> bool:
        """Tải danh sách nhân vật từ file JSON."""
        if not os.path.exists(filepath):
            app_logger.warning(f"File không tồn tại: {filepath}")
            return False
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            self.characters = {}
            for char_id, char_data in data.items():
                self.characters[char_id] = Character.from_dict(char_data)
                
            app_logger.info(f"Đã tải {len(self.characters)} nhân vật từ: {filepath}")
            return True
        except Exception as e:
            app_logger.error(f"Lỗi khi tải danh sách nhân vật: {str(e)}")
            return False
            
    def auto_detect_characters(self, script_text: str) -> List[Character]:
        """
        Sử dụng AI (GeminiProvider) để phân tích kịch bản và 
        tự động phát hiện/tạo các nhân vật với mô tả nhất quán.
        """
        provider = GeminiProvider()
        
        system_instruction = (
            "You are an expert character designer and casting director. "
            "Analyze the following video script and identify all key characters. "
            "For each character, generate a detailed, consistent visual description. "
            "All descriptions MUST be in English. "
            "Return the output STRICTLY as a JSON array of objects, where each object has these exact keys: "
            "'id' (like CHAR_001), 'name' (display name), 'age' (e.g., '65-year-old'), "
            "'gender' (e.g., 'man', 'woman'), 'face' (detailed face description), "
            "'hair' (color, style, length), 'clothing' (outfit description), "
            "'body_type' (e.g., 'medium', 'slim', 'muscular'), 'personality' (mood/expression), "
            "'visual_style' (e.g., 'cinematic', 'photorealistic'), "
            "'custom_tags' (array of additional appearance keywords in English)."
        )
        
        prompt = f"Script to analyze:\n\n{script_text}\n\nIdentify the characters and return the JSON array."
        
        try:
            app_logger.info("Đang gọi AI để phân tích và trích xuất thông tin nhân vật từ kịch bản...")
            response_json_str = provider.generate(system_instruction, prompt)
            
            # Làm sạch chuỗi JSON nếu cần
            clean_str = response_json_str.strip()
            if clean_str.startswith("```json"):
                clean_str = clean_str[7:]
            if clean_str.endswith("```"):
                clean_str = clean_str[:-3]
            clean_str = clean_str.strip()
                
            characters_data = json.loads(clean_str)
            detected_characters = []
            
            for item in characters_data:
                char = Character.from_dict(item)
                detected_characters.append(char)
                self.add_character(char)
                
            app_logger.info(f"Đã phát hiện tự động {len(detected_characters)} nhân vật.")
            return detected_characters
            
        except Exception as e:
            app_logger.error(f"Lỗi khi auto-detect characters bằng AI: {str(e)}")
            return []
