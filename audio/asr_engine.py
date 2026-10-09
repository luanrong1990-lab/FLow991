"""
audio/asr_engine.py - Nhận diện giọng nói (ASR) bằng Faster-Whisper.

Trích xuất timestamps (thời gian bắt đầu, kết thúc) cho từng từ.
Nhóm các từ lại thành các Segment (Câu/Phân đoạn ngữ nghĩa) dựa trên dấu câu và khoảng nghỉ.
"""

from config.config_manager import load_settings
from utils.logger import app_logger

class ASREngine:
    def __init__(self, model_size="base"):
        self.model_size = model_size
        self.model = None
        
    def _load_model(self):
        """Tải mô hình faster-whisper. Thiết lập GPU/CPU theo cấu hình."""
        if self.model is None:
            try:
                from faster_whisper import WhisperModel
                
                settings = load_settings()
                device_pref = settings.get("ASR_DEVICE", "cpu")
                
                device = "cuda" if device_pref == "gpu" else "cpu"
                compute_type = "float16" if device == "cuda" else "int8"
                
                app_logger.info(f"Đang tải mô hình Faster-Whisper ({self.model_size}) trên {device.upper()} (Compute: {compute_type})...")
                
                self.model = WhisperModel(self.model_size, device=device, compute_type=compute_type)
                app_logger.info("Tải mô hình Whisper thành công.")
            except ImportError:
                app_logger.error("Chưa cài đặt faster-whisper. Hãy chạy: pip install faster-whisper")
                raise RuntimeError("Thiếu thư viện faster-whisper. Vui lòng cài đặt trước.")
            except Exception as e:
                app_logger.error(f"Lỗi khi tải mô hình Whisper trên {device_pref}: {str(e)}")
                raise RuntimeError(f"Lỗi khởi tạo mô hình trên {device_pref}: {str(e)}")

    def analyze_audio(self, audio_path: str) -> list:
        """
        Nhận diện âm thanh và trả về danh sách các Segment.
        Mỗi Segment bao gồm: ID, start, end, text
        """
        settings = load_settings()
        device_pref = settings.get("ASR_DEVICE", "cpu")
        
        if device_pref == "groq":
            return self._analyze_via_groq(audio_path, settings.get("GROQ_API_KEY", ""))
        else:
            return self._analyze_via_local(audio_path)
            
    def _analyze_via_groq(self, audio_path: str, api_keys_str: str) -> list:
        import requests
        import os
        import random
        
        if not api_keys_str:
            raise ValueError("Chưa cấu hình Groq API Key trong Settings.")
            
        keys = [k.strip() for k in api_keys_str.split(",") if k.strip()]
        if not keys:
            raise ValueError("Chuỗi Groq API Key không hợp lệ.")
            
        selected_key = random.choice(keys)
            
        app_logger.info(f"Đang gửi file {audio_path} lên Groq Cloud (Sử dụng 1 trong {len(keys)} keys)...")
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {selected_key}"
        }
        
        with open(audio_path, "rb") as f:
            files = {
                "file": (os.path.basename(audio_path), f, "audio/wav")
            }
            data = {
                "model": "whisper-large-v3-turbo",
                "response_format": "verbose_json"
            }
            try:
                # Timeout khá dài vì upload có thể lâu
                response = requests.post(url, headers=headers, files=files, data=data, timeout=120)
                if response.status_code != 200:
                    raise Exception(f"Lỗi API Groq ({response.status_code}): {response.text}")
            except Exception as e:
                app_logger.error(f"Lỗi khi gọi Groq API: {str(e)}")
                raise RuntimeError(f"Lỗi khi gửi dữ liệu lên Groq: {str(e)}")
                
        res_json = response.json()
        final_segments = []
        
        # Lấy dữ liệu segments từ Groq (Xử lý trường hợp Groq trả về null cho segments)
        groq_segments = res_json.get("segments") or []
        for idx, segment in enumerate(groq_segments):
            text = segment.get("text", "").strip()
            if not text:
                continue
            final_segments.append({
                "id": f"SEG_{idx+1:04d}",
                "start": round(segment.get("start", 0.0), 2),
                "end": round(segment.get("end", 0.0), 2),
                "duration": round(segment.get("end", 0.0) - segment.get("start", 0.0), 2),
                "text": text
            })
            
        app_logger.info(f"Groq API phân tích hoàn tất. Có tổng cộng {len(final_segments)} segments.")
        return self._post_process_segments(final_segments)

    def _post_process_segments(self, segments: list, max_duration: float = 7.5) -> list:
        """
        Xử lý hậu kỳ: Cắt nhỏ các đoạn thoại quá dài (> max_duration) 
        để có nhiều khung hình hơn (giải quyết vấn đề 1 đoạn voice dài chỉ có 1 ảnh).
        """
        import math
        
        processed = []
        seg_index = 1
        
        for seg in segments:
            duration = seg.get("duration", 0.0)
            if duration <= max_duration:
                # Đánh lại ID cho chuẩn
                seg["id"] = f"SEG_{seg_index:04d}"
                processed.append(seg)
                seg_index += 1
                continue
                
            # Đoạn này quá dài, cần cắt nhỏ
            start = seg.get("start", 0.0)
            text = seg.get("text", "").strip()
            
            num_chunks = math.ceil(duration / max_duration)
            words = text.split()
            total_words = len(words)
            
            if total_words < num_chunks:
                seg["id"] = f"SEG_{seg_index:04d}"
                processed.append(seg)
                seg_index += 1
                continue
                
            words_per_chunk = total_words // num_chunks
            
            for i in range(num_chunks):
                # Tính toán word index
                chunk_start_idx = i * words_per_chunk
                if i == num_chunks - 1:
                    chunk_end_idx = total_words
                else:
                    # Cố gắng tìm dấu phẩy hoặc chấm để ngắt
                    best_break = chunk_start_idx + words_per_chunk
                    for j in range(chunk_start_idx + 1, min(chunk_start_idx + words_per_chunk + 4, total_words)):
                        if any(p in words[j-1] for p in ['.', ',', '!', '?', ';', ':']):
                            best_break = j
                            break
                    chunk_end_idx = best_break
                    
                # Cắt text
                chunk_words = words[chunk_start_idx:chunk_end_idx]
                if not chunk_words:
                    continue
                chunk_text = " ".join(chunk_words)
                
                # Nội suy timeline theo tỷ lệ số từ
                chunk_start_time = start + (chunk_start_idx / total_words) * duration
                chunk_end_time = start + (chunk_end_idx / total_words) * duration
                
                # Cắt words array nếu có
                seg_words = seg.get("words", [])
                chunk_word_objs = []
                if seg_words and len(seg_words) == total_words:
                    chunk_word_objs = seg_words[chunk_start_idx:chunk_end_idx]
                    if chunk_word_objs:
                        chunk_start_time = chunk_word_objs[0]["start"]
                        chunk_end_time = chunk_word_objs[-1]["end"]
                
                processed.append({
                    "id": f"SEG_{seg_index:04d}",
                    "start": round(chunk_start_time, 2),
                    "end": round(chunk_end_time, 2),
                    "duration": round(chunk_end_time - chunk_start_time, 2),
                    "text": chunk_text,
                    "words": chunk_word_objs
                })
                seg_index += 1
                
        app_logger.info(f"Post-processing: Đã tách thành {len(processed)} segments (Max duration: {max_duration}s).")
        return processed

    def _analyze_via_local(self, audio_path: str) -> list:
        self._load_model()
        
        app_logger.info(f"Bắt đầu nhận diện ASR cho file: {audio_path}")
        try:
            # word_timestamps=True là bắt buộc để lấy chính xác thời gian từng chữ
            segments_generator, info = self.model.transcribe(
                audio_path, 
                beam_size=5, 
                word_timestamps=True,
                vad_filter=True # Lọc khoảng lặng
            )
            
            app_logger.info(f"Ngôn ngữ phát hiện: {info.language} (Độ tin cậy: {info.language_probability})")
            
            final_segments = []
            segment_index = 1
            
            # Gộp các từ thành từng câu nhỏ (Semantic Segmentation)
            for segment in segments_generator:
                text = segment.text.strip()
                if not text:
                    continue
                    
                word_list = []
                if hasattr(segment, 'words') and segment.words:
                    for w in segment.words:
                        word_list.append({
                            "word": w.word.strip(),
                            "start": round(w.start, 2),
                            "end": round(w.end, 2)
                        })
                
                final_segments.append({
                    "id": f"SEG_{segment_index:04d}",
                    "start": round(segment.start, 2),
                    "end": round(segment.end, 2),
                    "duration": round(segment.end - segment.start, 2),
                    "text": text,
                    "words": word_list
                })
                segment_index += 1
                
            app_logger.info(f"Phân tích hoàn tất. Có tổng cộng {len(final_segments)} segments.")
            return self._post_process_segments(final_segments)
            
        except Exception as e:
            app_logger.error(f"Lỗi khi chạy ASR local: {str(e)}")
            raise
