import os
from utils.logger import app_logger

class SubtitleEngine:
    def __init__(self, project_dir):
        self.output_dir = os.path.join(project_dir, "subtitles")
        os.makedirs(self.output_dir, exist_ok=True)
        
    def generate_ass(self, segments: list, filename="subtitles.ass"):
        """
        Sinh file .ass chứa phụ đề Karaoke.
        """
        ass_path = os.path.join(self.output_dir, filename)
        
        header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Arial,80,&H0000FFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,10,10,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        lines = [header]
        
        def format_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = seconds % 60
            return f"{h:01d}:{m:02d}:{s:05.2f}"
            
        for seg in segments:
            start_time = format_time(seg["start"])
            end_time = format_time(seg["end"])
            
            words = seg.get("words", [])
            text_parts = []
            
            if not words:
                text_parts.append(seg.get("text", ""))
            else:
                for w in words:
                    w_dur = w["end"] - w["start"]
                    # k is centiseconds (1/100 of sec)
                    centisecs = int(w_dur * 100)
                    # Use {\k} for karaoke fill effect
                    text_parts.append(f"{{\\k{centisecs}}}{w['word']}")
                    
            text_line = " ".join(text_parts)
            # ASS Dialogue line
            line = f"Dialogue: 0,{start_time},{end_time},Karaoke,,0,0,0,,{text_line}\n"
            lines.append(line)
            
        try:
            with open(ass_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            app_logger.info(f"Đã tạo file phụ đề ASS: {ass_path}")
            return ass_path
        except Exception as e:
            app_logger.error(f"Lỗi tạo subtitle ASS: {e}")
            return ""
