"""
audio/audio_manager.py - Quản lý việc xử lý và ghép nối file âm thanh.

Sử dụng FFmpeg để ghép nối nhiều file âm thanh nhỏ thành 1 file duy nhất.
Tự động chuyển đổi format về WAV 16kHz Mono chuẩn cho Whisper.
"""

import os
import tempfile
import subprocess
from utils.logger import app_logger

class AudioManager:
    @staticmethod
    def concatenate_audio_files(input_files: list, output_path: str) -> bool:
        """
        Ghép nhiều file âm thanh thành 1 file duy nhất.
        Sử dụng FFmpeg concat demuxer.
        Trả về True nếu thành công, False nếu lỗi.
        """
        if not input_files:
            app_logger.warning("Không có file âm thanh nào để ghép nối.")
            return False
            
        if len(input_files) == 1:
            app_logger.info("Chỉ có 1 file, tiến hành chuyển đổi định dạng.")
            return AudioManager._convert_to_wav(input_files[0], output_path)

        # Tạo file danh sách tạm thời cho ffmpeg
        list_file_fd, list_file_path = tempfile.mkstemp(suffix=".txt", text=True)
        try:
            with os.fdopen(list_file_fd, 'w', encoding='utf-8') as f:
                for file_path in input_files:
                    # ffmpeg yêu cầu escape đường dẫn hoặc dùng path tương đối/tuyệt đối chuẩn
                    safe_path = file_path.replace("\\", "/")
                    f.write(f"file '{safe_path}'\n")
            
            app_logger.info(f"Đã tạo file danh sách ghép nối: {list_file_path}")
            
            # Lệnh FFmpeg: Ghép nối và convert sang WAV 16kHz Mono (Chuẩn tốt nhất cho ASR Whisper)
            cmd = [
                "ffmpeg",
                "-y",                   # Overwrite output
                "-f", "concat",         # Dùng concat demuxer
                "-safe", "0",           # Bỏ qua cảnh báo đường dẫn
                "-i", list_file_path,   # File danh sách
                "-c:a", "pcm_s16le",    # Codec âm thanh: PCM 16-bit
                "-ar", "16000",         # Sample rate: 16kHz
                "-ac", "1",             # Channels: Mono
                output_path
            ]
            
            app_logger.info(f"Đang chạy FFmpeg: {' '.join(cmd)}")
            
            # Ẩn cửa sổ console trên Windows
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            process = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True,
                startupinfo=startupinfo
            )
            
            if process.returncode == 0:
                app_logger.info(f"Ghép nối âm thanh thành công: {output_path}")
                return True
            else:
                app_logger.error(f"Lỗi FFmpeg: {process.stderr}")
                return False
                
        except Exception as e:
            app_logger.error(f"Lỗi khi ghép nối âm thanh: {str(e)}")
            return False
        finally:
            # Dọn dẹp file tạm
            try:
                os.remove(list_file_path)
            except OSError:
                pass

    @staticmethod
    def _convert_to_wav(input_path: str, output_path: str) -> bool:
        """
        Chuyển đổi 1 file sang WAV 16kHz Mono.
        """
        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-c:a", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            output_path
        ]
        
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        try:
            process = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True,
                startupinfo=startupinfo
            )
            
            if process.returncode == 0:
                app_logger.info(f"Chuyển đổi âm thanh thành công: {output_path}")
                return True
            else:
                app_logger.error(f"Lỗi FFmpeg convert: {process.stderr}")
                return False
        except Exception as e:
            app_logger.error(f"Lỗi khi convert âm thanh: {str(e)}")
            return False
