"""
ai/gemini_provider.py - Triển khai AIProvider cho Google Gemini.

Sử dụng REST API của Google Generative Language.
Tự động lấy Random API Key và Model từ file config.
Sinh ra nội dung Lời thoại + SEO Metadata (JSON) theo Phase 2.
"""

import requests
import json
from ai.base import AIProvider
from config.config_manager import load_settings, get_random_api_key
from utils.logger import app_logger

class GeminiProvider(AIProvider):
    def __init__(self):
        self.provider_name = "Gemini (Google)"
        
    def generate_script(
        self, 
        topic: str, 
        audience: str = "Tất cả", 
        style: str = "Tự nhiên",
        language: str = "Tiếng Việt",
        duration: str = "1 - 3 phút"
    ) -> str:
        api_key = get_random_api_key(self.provider_name)
        if not api_key:
            raise ValueError(f"Không tìm thấy API Key nào cho {self.provider_name}. Vui lòng cập nhật trong Settings.")
            
        settings = load_settings()
        model = settings.get(f"{self.provider_name}_MODEL", "models/gemini-2.5-flash")
        
        if not model.startswith("models/"):
            model = f"models/{model}"
            
        system_instruction = (
            "Bạn là một biên kịch video chuyên nghiệp và chuyên gia SEO YouTube. "
            f"YÊU CẦU NGÔN NGỮ TỐI THƯỢNG: Kịch bản và toàn bộ thông tin SEO PHẢI được viết bằng ngôn ngữ: {language}. "
            "Hãy đảm bảo ngữ pháp và văn phong tự nhiên chuẩn xác của người bản địa (Native Speaker).\n\n"
        )
        
        # Inject Japanese Faceless Video Rules if target is Japanese
        if "Nhật" in language or "Japanese" in language:
            system_instruction += (
                "--- JAPANESE FACELESS VIDEO RULES ---\n"
                "1. Bạn đang viết kịch bản cho kênh YouTube/TikTok Nhật Bản dạng Faceless (thường dùng giọng Zundamon hoặc Yukkuri).\n"
                "2. Cấu trúc bắt buộc: HOOK (3 giây đầu cực sốc) -> BODY (Giải quyết vấn đề nhanh gọn) -> CTA (Kêu gọi đăng ký kênh).\n"
                "3. Văn phong: Sử dụng văn nói (Spoken Japanese - 口語), thân thiện, dễ nghe. Thỉnh thoảng có các từ cảm thán (ええっ, なるほど, すごい).\n"
                "4. KHÔNG sử dụng kính ngữ quá trang trọng (Keigo/Kenjougo) trừ khi đó là kênh tin tức nghiêm túc. Hãy dùng thể Desu/Masu (です/ます) hoặc thể thân mật (だ/である) tùy theo style.\n"
                "--------------------------------------\n\n"
            )

        system_instruction += (
            "Nhiệm vụ của bạn là:\n"
            "1. Viết kịch bản LỜI THOẠI (Voiceover) hấp dẫn, tự nhiên dựa trên chủ đề/bài báo, "
            f"TUÂN THỦ CHẶT CHẼ đối tượng khán giả và phong cách được yêu cầu. "
            f"Thời lượng dự kiến của video là: {duration}. Hãy căn chỉnh độ dài của kịch bản cho phù hợp với thời lượng này. "
            "CHỈ viết nội dung lời thoại, KHÔNG mô tả hình ảnh, KHÔNG chia cảnh.\n"
            "2. Tạo 5 tiêu đề video thu hút (Clickable titles).\n"
            "3. Viết 1 đoạn mô tả (Description) chuẩn SEO.\n"
            "4. Cung cấp danh sách các từ khóa (Tags) và Hashtags.\n\n"
            f"BẠN PHẢI TRẢ VỀ KẾT QUẢ DƯỚI DẠNG CHUẨN JSON VỚI CẤU TRÚC SAU (chữ khóa JSON giữ nguyên tiếng Anh, nội dung dùng ngôn ngữ {language}):\n"
            "{\n"
            '  "script": "Toàn bộ nội dung lời thoại (xuống dòng bằng \\n\\n)",\n'
            '  "titles": ["Tiêu đề 1", "Tiêu đề 2", "Tiêu đề 3", "Tiêu đề 4", "Tiêu đề 5"],\n'
            '  "description": "Mô tả video",\n'
            '  "tags": ["tag1", "tag2", "tag3"],\n'
            '  "hashtags": ["#hash1", "#hash2"]\n'
            "}"
        )
        
        topic_content = topic
        if topic.startswith("http://") or topic.startswith("https://"):
            try:
                resp = requests.get(topic, timeout=10)
                if resp.status_code == 200:
                    topic_content = f"Nội dung từ URL ({topic}):\n\n{resp.text[:10000]}"
            except Exception as e:
                app_logger.warning(f"Không thể tải URL: {str(e)}")
        
        final_prompt = (
            f"Chủ đề / Bài báo: {topic_content}\n"
            f"Đối tượng khán giả (Target Audience): {audience}\n"
            f"Phong cách kịch bản (Style/Tone): {style}\n"
            f"Thời lượng (Duration): {duration}\n"
            f"Ngôn ngữ (Language): {language}"
        )
        
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": final_prompt}]
                }
            ],
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 8192,
                "responseMimeType": "application/json"
            }
        }
        
        # Lấy danh sách keys để retry nếu gặp 503 hoặc 429
        keys_str = settings.get(f"{self.provider_name}_API_KEYS", "")
        all_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        if not all_keys:
            all_keys = [api_key]
            
        candidate_models = [model]
        for fallback in ["models/gemini-2.5-flash", "models/gemini-3.5-flash"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)
                
        last_error = ""
        for cur_model in candidate_models:
            for cur_key in all_keys:
                cur_url = f"https://generativelanguage.googleapis.com/v1beta/{cur_model}:generateContent?key={cur_key}"
                try:
                    app_logger.info(f"Đang gọi {cur_model} (Key: {cur_key[:5]}...) để tạo Kịch bản ({language}, {duration}).")
                    headers = {"Content-Type": "application/json"}
                    response = requests.post(cur_url, headers=headers, json=payload, timeout=120)
                    
                    if response.status_code == 200:
                        data = response.json()
                        script_json_str = data['candidates'][0]['content']['parts'][0]['text']
                        app_logger.info(f"Đã tạo xong kịch bản & SEO thành công với {cur_model}.")
                        return script_json_str
                    else:
                        last_error = f"HTTP {response.status_code}: {response.text[:120]}"
                        app_logger.warning(f"{cur_model} trả về mã {response.status_code}. Đang tự động đổi key/model...")
                except Exception as ex:
                    last_error = str(ex)
                    app_logger.warning(f"Lỗi khi gọi {cur_model}: {ex}")
                    
        raise RuntimeError(f"Tất cả key và model Gemini đều quá tải (503/429). Chi tiết: {last_error}")

    def generate(self, system_instruction: str, prompt: str) -> str:
        settings = load_settings()
        keys_str = settings.get(f"{self.provider_name}_API_KEYS", "")
        all_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        if not all_keys:
            api_key = get_random_api_key(self.provider_name)
            all_keys = [api_key] if api_key else []
            
        if not all_keys:
            raise ValueError(f"Không tìm thấy API Key cho {self.provider_name}.")
            
        model = settings.get(f"{self.provider_name}_MODEL", "models/gemini-2.5-flash")
        if not model.startswith("models/"):
            model = f"models/{model}"
            
        candidate_models = [model]
        for fallback in ["models/gemini-2.5-flash", "models/gemini-3.5-flash"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)
        
        payload = {
            "system_instruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "topP": 0.95,
                "topK": 40,
                "response_mime_type": "application/json"
            }
        }
        headers = {"Content-Type": "application/json"}
        last_error = ""
        
        for cur_model in candidate_models:
            for cur_key in all_keys:
                cur_url = f"https://generativelanguage.googleapis.com/v1beta/{cur_model}:generateContent?key={cur_key}"
                try:
                    response = requests.post(cur_url, headers=headers, json=payload, timeout=60)
                    if response.status_code == 200:
                        res_json = response.json()
                        candidates = res_json.get("candidates", [])
                        if candidates:
                            return candidates[0]["content"]["parts"][0]["text"].strip()
                    else:
                        last_error = f"HTTP {response.status_code}: {response.text[:120]}"
                except Exception as ex:
                    last_error = str(ex)
                    
        raise RuntimeError(f"Lỗi kết nối Gemini API (503/429): {last_error}")

    def analyze_image_style(self, image_path: str) -> str:
        """
        Phân tích phong cách nghệ thuật của một bức ảnh bằng Gemini Vision.
        Trả về chuỗi mô tả style ngắn gọn (tiếng Anh) để dùng làm Visual Style.
        Ví dụ: "Photorealistic, cinematic lighting, warm color grading"
        """
        import base64
        import mimetypes
        
        settings = load_settings()
        keys_str = settings.get(f"{self.provider_name}_API_KEYS", "")
        all_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        if not all_keys:
            api_key = get_random_api_key(self.provider_name)
            all_keys = [api_key] if api_key else []
            
        if not all_keys:
            raise ValueError(f"Không tìm thấy API Key cho {self.provider_name}.")
            
        model = settings.get(f"{self.provider_name}_MODEL", "models/gemini-2.5-flash")
        if not model.startswith("models/"):
            model = f"models/{model}"
            
        # Đọc ảnh và chuyển sang base64
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = "image/png"
            
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        
        # Prompt yêu cầu phân tích style
        system_instruction = (
            "You are an expert art critic and visual style analyst. "
            "Analyze the provided image and describe its visual/artistic style in a concise phrase (in English). "
            "Focus on: rendering technique, lighting style, color palette, and art movement. "
            "Return ONLY a short style description (max 10 words) that can be used as an image generation style directive. "
            "Examples of good responses:\n"
            "- 'Photorealistic, cinematic lighting, warm tones'\n"
            "- 'Anime style, vibrant colors, cel shading'\n"
            "- 'Oil painting, impressionist, soft brushstrokes'\n"
            "- 'Dark moody noir, high contrast, desaturated'\n"
            "- 'Watercolor illustration, pastel palette, dreamy'\n"
            "Do NOT include subject description. ONLY describe the art style/technique."
        )
        
        payload = {
            "system_instruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_data
                            }
                        },
                        {
                            "text": "Analyze this image and describe its visual art style in a short phrase."
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 100
            }
        }
        
        headers = {"Content-Type": "application/json"}
        candidate_models = [model]
        for fallback in ["models/gemini-2.5-flash", "models/gemini-3.5-flash"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)
                
        last_error = ""
        for cur_model in candidate_models:
            for cur_key in all_keys:
                url = f"https://generativelanguage.googleapis.com/v1beta/{cur_model}:generateContent?key={cur_key}"
                try:
                    app_logger.info(f"Đang gửi ảnh tới Gemini ({cur_model}, key: {cur_key[:5]}...) để phân tích style...")
                    response = requests.post(url, headers=headers, json=payload, timeout=60)
                    if response.status_code == 200:
                        res_json = response.json()
                        candidates = res_json.get("candidates", [])
                        if candidates:
                            style_text = candidates[0]["content"]["parts"][0]["text"].strip()
                            style_text = style_text.strip('"\'')
                            app_logger.info(f"Phân tích style thành công với {cur_model}: {style_text}")
                            return style_text
                    else:
                        last_error = f"HTTP {response.status_code}: {response.text[:100]}"
                except Exception as ex:
                    last_error = str(ex)
                    
        raise RuntimeError(f"Lỗi phân tích style ảnh qua Gemini: {last_error}")
