"""
visual/prompt_engine.py - Engine sinh Visual Prompts dựa trên kịch bản và phân đoạn ASR.
"""
import json
from ai.gemini_provider import GeminiProvider
from utils.logger import app_logger

class VisualPromptEngine:
    def __init__(self):
        self.ai = GeminiProvider()

    def generate_prompts(self, script_text: str, segments: list, character_descriptions: str = '') -> list:
        # Xây dựng instruction cơ bản
        system_instruction = (
            "You are an expert AI Video Director and Prompt Engineer.\n"
            "Your task is to generate highly detailed, cinematic Image Prompts (in English) for EACH audio segment in a video.\n"
        )
        
        if character_descriptions:
            system_instruction += (
                "\nCRITICAL: CHARACTER CONSISTENCY REQUIRED.\n"
                "You MUST use the following exact character descriptions whenever the character appears.\n"
                f"{character_descriptions}\n"
            )
            
        system_instruction += (
            "\nWhen creating prompts, ensure they explicitly include the following elements when applicable:\n"
            "- Subject: Detailed description of the main subject.\n"
            "- Environment: The setting or background.\n"
            "- Lighting: Type of lighting (e.g., cinematic, natural, neon, moody).\n"
            "- Camera: Shot type and camera settings (e.g., close-up, wide shot, shallow depth of field).\n"
            "- Composition: How elements are arranged in the frame.\n"
            "- Mood: Emotional tone of the image.\n"
            "- Time period / Visual style: Specific era or artistic style (e.g., cyberpunk, photorealistic, vintage).\n"
            "\nCRITICAL TIMELINE INSTRUCTION:\n"
            "You will be provided with the Duration (in seconds) for each segment.\n"
            "Use this duration to understand how much visual weight or complexity the static image needs to carry, "
            "but DO NOT include video-specific camera movements (like pan, zoom) in your prompt. The prompt MUST be strictly for a STATIC image.\n"
            "\nDo not include weird text in the prompt unless necessary.\n"
            "\nFormat your response as a valid JSON array of objects:\n"
            "[\n"
            '  {"id": "segment_id", "prompt": "Your detailed image prompt here..."}\n'
            "]\n"
        )
        
        context_script = script_text[:2000] if script_text else "No context provided."
        
        # Hàm xử lý 1 chunk
        def process_chunk(chunk):
            user_prompt = f"Context Script:\n{context_script}\n\nSegments to generate prompts for:\n"
            for seg in chunk:
                duration = seg.get('duration', 0.0)
                dur_str = f" | Duration: {duration}s" if duration > 0 else ""
                user_prompt += f"ID: {seg['id']}{dur_str} | Text: {seg['text']}\n"
                
            try:
                # Tạo instance riêng lẻ để mỗi luồng bốc 1 key ngẫu nhiên an toàn
                local_ai = GeminiProvider()
                result_json_str = local_ai.generate(system_instruction, user_prompt)
                clean_str = result_json_str.replace("```json", "").replace("```", "").strip()
                return json.loads(clean_str)
            except Exception as e:
                app_logger.error(f"Lỗi phân tích JSON từ AI (Chunk {chunk[0]['id']}): {e}")
                return []

        import concurrent.futures
        
        CHUNK_SIZE = 15
        chunks = [segments[i:i + CHUNK_SIZE] for i in range(0, len(segments), CHUNK_SIZE)]
        
        app_logger.info(f"Đang gửi AI sinh Prompts ({len(segments)} segments chia thành {len(chunks)} lô đồng thời)...")
        
        final_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_chunk = {executor.submit(process_chunk, chunk): chunk for chunk in chunks}
            for future in concurrent.futures.as_completed(future_to_chunk):
                try:
                    data = future.result()
                    if isinstance(data, list):
                        final_results.extend(data)
                except Exception as exc:
                    app_logger.error(f"Lỗi khi thực thi luồng sinh prompt: {exc}")
                    
        return final_results

    def generate_prompts_with_characters(self, script_text: str, segments: list, character_manager) -> list:
        """
        Sinh prompts với thông tin nhân vật được tự động lấy từ CharacterManager.
        Phương thức tiện ích: gọi build_all_descriptions() và truyền vào generate_prompts().
        """
        char_desc_str = character_manager.build_all_descriptions()
        char_count = len(character_manager.get_all_characters())
        
        app_logger.info(f"Đã lấy mô tả của {char_count} nhân vật từ CharacterManager.")
        
        return self.generate_prompts(script_text, segments, character_descriptions=char_desc_str)
