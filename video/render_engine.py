import os
import subprocess
import math
import shutil
from utils.logger import app_logger

class RenderEngine:
    def __init__(self, project_dir):
        self.project_dir = project_dir
        self.output_dir = os.path.join(project_dir, "exports")
        self.temp_dir = os.path.join(project_dir, "temp_render")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        
    def _get_ffmpeg_cmd(self):
        # Giả định ffmpeg đã có trong PATH
        return "ffmpeg"

    def _run_ffmpeg(self, cmd, **kwargs):
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, **kwargs)
        if result.returncode:
            error = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"FFmpeg thất bại: {error[-6000:]}")
        
    def render(self, segments, audio_path, subtitle_path, output_filename="final_video.mp4", *, bgm_path=None, font_path=None, cancelled=None):
        """
        Render final video từ các ảnh, audio và subtitle.
        """
        output_path = os.path.join(self.output_dir, output_filename)
        cancelled = cancelled or (lambda: False)
        if not segments:
            raise ValueError("Không có phân đoạn để render.")
        if not audio_path or not os.path.isfile(audio_path):
            raise ValueError("Không tìm thấy file âm thanh.")
        if subtitle_path and not os.path.isfile(subtitle_path):
            raise ValueError("Không tìm thấy file phụ đề.")
        if bgm_path and not os.path.isfile(bgm_path):
            raise ValueError("Không tìm thấy nhạc nền.")
        for seg in segments:
            duration = float(seg.get("duration", 0))
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError("Thời lượng mỗi phân đoạn phải lớn hơn 0 và hữu hạn.")
        
        # 1. Sinh các video clip ngắn từ từng image
        clip_paths = []
        for i, seg in enumerate(segments):
            if cancelled():
                raise InterruptedError("Đã dừng xuất video.")
            img_path = seg.get("image_path")
            dur = float(seg.get("duration", 0.0))
            effect = seg.get("effect", "")
            
            if not img_path or not os.path.exists(img_path):
                app_logger.error(f"Lỗi: Không tìm thấy ảnh cho segment {seg.get('id')}")
                return False
                
            clip_path = os.path.join(self.temp_dir, f"clip_{i:04d}.mp4")
            clip_paths.append(clip_path)
            
            # Xây dựng FFmpeg filter cho hiệu ứng
            # Frame rate 30fps
            vf = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1"
            
            if effect == "Random":
                import random
                effect = random.choice(["Zoom In", "Zoom Out", "Pan Left", "Pan Right", "Pan Up", "Pan Down"])
                
            if effect == "Zoom In":
                # Phóng to nhẹ từ từ (zoom 1.0 to 1.15)
                vf += ",zoompan=z='min(zoom+0.001,1.15)':d={}:s=1920x1080:fps=30".format(int(dur*30))
            elif effect == "Zoom Out":
                # Thu nhỏ từ từ (zoom 1.15 to 1.0)
                vf += ",zoompan=z='1.15-on*0.001':d={}:s=1920x1080:fps=30".format(int(dur*30))
            elif effect == "Pan Left":
                vf += ",zoompan=z=1.15:x='max(0, x-1)':y='y':d={}:s=1920x1080:fps=30".format(int(dur*30))
            elif effect == "Pan Right":
                vf += ",zoompan=z=1.15:x='x+1':y='y':d={}:s=1920x1080:fps=30".format(int(dur*30))
            elif effect == "Pan Up":
                vf += ",zoompan=z=1.15:x='x':y='max(0, y-1)':d={}:s=1920x1080:fps=30".format(int(dur*30))
            elif effect == "Pan Down":
                vf += ",zoompan=z=1.15:x='x':y='y+1':d={}:s=1920x1080:fps=30".format(int(dur*30))
            else:
                # Tĩnh
                vf += f",format=yuv420p"

            cmd = [
                self._get_ffmpeg_cmd(), "-y",
                "-loop", "1",
                "-i", img_path,
                "-t", str(dur),
                "-vf", vf,
                "-c:v", "libx264",
                "-preset", "ultrafast", 
                "-pix_fmt", "yuv420p",
                "-r", "30",
                clip_path
            ]
            
            app_logger.info(f"Đang render clip {i+1}/{len(segments)}...")
            self._run_ffmpeg(cmd)
            
        # 2. Nối các video clip
        concat_list_path = os.path.join(self.temp_dir, "concat_list.txt")
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for cp in clip_paths:
                safe_path = os.path.abspath(cp).replace(chr(92), '/').replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")
                
        merged_video = os.path.join(self.temp_dir, "merged_video_no_audio.mp4")
        concat_cmd = [
            self._get_ffmpeg_cmd(), "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",
            merged_video
        ]
        app_logger.info("Đang ghép nối các clip hình ảnh...")
        self._run_ffmpeg(concat_cmd)
        
        # 3. Add audio and subtitles
        app_logger.info("Đang thêm Audio và Karaoke Subtitles...")
        
        # Sửa đường dẫn subtitle cho FFmpeg filter (dùng đường dẫn tương đối để tránh lỗi dấu hai chấm của ổ đĩa trên Windows)
        # A fixed local filename avoids filter escaping and cross-drive paths.
        if subtitle_path:
            shutil.copyfile(subtitle_path, os.path.join(self.temp_dir, "render_subtitles.ass"))
        if font_path:
            font_dir = os.path.join(self.temp_dir, "fonts")
            os.makedirs(font_dir, exist_ok=True)
            shutil.copyfile(font_path, os.path.join(font_dir, os.path.basename(font_path)))
        if cancelled():
            raise InterruptedError("Đã dừng xuất video.")
        pending_output = os.path.join(self.output_dir, "pending_" + os.path.basename(output_filename))
        ass_filter = "ass=render_subtitles.ass" + (":fontsdir=fonts" if font_path else "")
        
        final_cmd = [
            self._get_ffmpeg_cmd(), "-y",
            "-i", os.path.abspath(merged_video),
            "-i", os.path.abspath(audio_path),
            *(["-stream_loop", "-1", "-i", os.path.abspath(bgm_path)] if bgm_path else []),
            *(["-vf", ass_filter] if subtitle_path else []),
            *(["-filter_complex", "[1:a]asplit=2[voice][side];[2:a]volume=0.12[bg];[bg][side]sidechaincompress=threshold=0.03:ratio=8[duck];[voice][duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[mix]",
               "-map", "0:v:0", "-map", "[mix]"] if bgm_path else ["-map", "0:v:0", "-map", "1:a:0"]),
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            os.path.abspath(pending_output)
        ]
        
        self._run_ffmpeg(final_cmd, cwd=self.temp_dir)
        os.replace(pending_output, output_path)
        app_logger.info(f"Video đã render thành công tại: {output_path}")
        return output_path
