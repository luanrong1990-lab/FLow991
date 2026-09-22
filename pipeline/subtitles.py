"""
Generate karaoke-style .ass subtitles with telop overlays.
"""
from typing import Dict, List, Any
from pathlib import Path
from core.brand import VIDEO_WIDTH, VIDEO_HEIGHT, FONT_JP


def generate_ass(
    scenes: List[Dict[str, Any]],
    tts_results: List[Dict[str, Any]],
    output_path: Path
):
    """
    Generate .ass subtitle file with karaoke effects and telop.
    
    Args:
        scenes: Scenes with narration and telop
        tts_results: TTS results with marks (morpheme timing)
        output_path: Output .ass file path
    """
    # Build lookup: scene_id -> tts result
    tts_lookup = {t["scene_id"]: t for t in tts_results}
    
    lines = []
    
    # Header
    lines.append("[Script Info]")
    lines.append(f"Title: JP Faceless YouTube")
    lines.append(f"ScriptType: v4.00+")
    lines.append(f"PlayResX: {VIDEO_WIDTH}")
    lines.append(f"PlayResY: {VIDEO_HEIGHT}")
    lines.append("")
    
    # Styles
    lines.append("[V4+ Styles]")
    lines.append("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")
    
    # Kara style: white with orange secondary, black outline, bottom center
    lines.append(
        "Style: Kara,Noto Sans JP,84,&H00FFFFFF,&H0000B4FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,5,0,2,0,0,90,1"
    )
    
    # Telop style: yellow text on semi-transparent box, top center
    lines.append(
        "Style: Telop,Noto Sans JP,60,&H0000FFFF,&H00000000,&H00000000,&H80000000,1,0,0,0,100,100,0,0,3,3,0,8,0,0,680,1"
    )
    lines.append("")
    
    # Events
    lines.append("[Events]")
    lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")
    
    for scene in scenes:
        scene_id = scene.get("id")
        start = scene.get("start", 0)
        end = scene.get("end", 5)
        narration = scene.get("narration", "")
        telop = scene.get("telop", [])
        
        tts_data = tts_lookup.get(scene_id, {})
        marks = tts_data.get("marks", [])
        
        # Calculate relative start time within scene
        scene_start_ms = int(start * 100)
        
        # Generate karaoke line for narration
        if marks:
            karaoke_parts = []
            for i, (morph, t_seconds) in enumerate(marks):
                # Calculate duration to next morpheme
                if i + 1 < len(marks):
                    next_t = marks[i + 1][1]
                    dur_seconds = next_t - t_seconds
                else:
                    # Last morpheme: use remaining scene time
                    dur_seconds = end - (start + t_seconds)
                
                dur_cs = int(dur_seconds * 100)  # centi-seconds
                escaped = escape_ass_text(morph)
                karaoke_parts.append(f"{{\\kf{dur_cs}}}{escaped}")
            
            karaoke_text = "".join(karaoke_parts)
            
            # Dialogue line
            start_time = format_ass_time(start)
            end_time = format_ass_time(end)
            lines.append(
                f"Dialogue: 0,{start_time},{end_time},Kara,,0,0,0,,{karaoke_text}"
            )
        
        # Generate telop lines (appear sequentially)
        for j, telop_line in enumerate(telop):
            # Each telop appears at start+0.3+j*2.6, lasts 2.4s
            telop_start = start + 0.3 + j * 2.6
            telop_dur = 2.4
            telop_end = min(telop_start + telop_dur, end)
            
            if telop_start < telop_end:
                start_time = format_ass_time(telop_start)
                end_time = format_ass_time(telop_end)
                escaped = escape_ass_text(telop_line)
                lines.append(
                    f"Dialogue: 1,{start_time},{end_time},Telop,,0,0,0,,{escaped}"
                )
    
    # Write file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"Generated subtitles: {output_path}")


def escape_ass_text(text: str) -> str:
    """Escape special characters for ASS format."""
    # Escape curly braces (used for tags)
    text = text.replace("{", r"\{")
    text = text.replace("}", r"\}")
    return text


def format_ass_time(seconds: float) -> str:
    """Format seconds as ASS timestamp H:MM:SS.cc"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"
