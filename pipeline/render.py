"""
Final video rendering with ffmpeg and thumbnail generation.
"""
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from PIL import Image, ImageDraw, ImageFont

from core.brand import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS,
    THUMB_WIDTH, THUMB_HEIGHT,
    FONT_JP, FONT_JP_HEAVY
)
from pipeline.scenes import format_timestamp


def render_video(
    scenes: List[Dict[str, Any]],
    images: Dict[str, str],
    tts_results: List[Dict[str, Any]],
    ass_path: Path,
    output_dir: Path,
    output_name: str = "video_final.mp4"
) -> str:
    """
    Render final video by concatenating scenes with audio and subtitles.
    
    Args:
        scenes: Scenes with timing
        images: {scene_id: image_path}
        tts_results: TTS results with paths
        ass_path: Path to .ass subtitle file
        output_dir: Output directory
        output_name: Output filename
    
    Returns:
        Path to rendered video
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_name
    
    # Build clip list for ffmpeg concat
    clips = []
    audio_clips = []
    
    tts_lookup = {t["scene_id"]: t for t in tts_results}
    
    for scene in scenes:
        scene_id = scene.get("id")
        dur = scene.get("dur", 5)
        
        img_path = images.get(str(scene_id))
        if not img_path:
            print(f"Warning: No image for scene {scene_id}")
            continue
        
        # Create temp clip
        clip_path = output_dir / f"clip_{scene_id}.mp4"
        
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", img_path,
            "-t", str(dur),
            "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},format=yuv420p",
            "-r", str(VIDEO_FPS),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-an",
            str(clip_path)
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        clips.append(str(clip_path))
        
        # Audio clip
        tts_data = tts_lookup.get(scene_id)
        if tts_data:
            audio_clips.append(tts_data["path"])
    
    if not clips:
        raise ValueError("No clips to render")
    
    # Create concat file
    concat_file = output_dir / "clips.txt"
    with open(concat_file, "w") as f:
        for clip in clips:
            f.write(f"file '{clip}'\n")
    
    # Concatenate video clips
    concat_video = output_dir / "concat_video.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(concat_video)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    
    # Concatenate audio files
    concat_audio = output_dir / "concat_audio.mp3"
    if audio_clips:
        audio_concat_file = output_dir / "audio_clips.txt"
        with open(audio_concat_file, "w") as f:
            for audio in audio_clips:
                f.write(f"file '{audio}'\n")
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(audio_concat_file),
            "-c", "aac",
            str(concat_audio)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
    else:
        concat_audio = None
    
    # Merge video + audio + subtitles
    if concat_audio:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(concat_video),
            "-i", str(concat_audio),
            "-vf", f"ass={ass_path}",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest",
            str(output_path)
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(concat_video),
            "-vf", f"ass={ass_path}",
            "-c:v", "libx264",
            "-c:a", "aac",
            str(output_path)
        ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    
    # Cleanup temp files
    for clip in clips:
        Path(clip).unlink(missing_ok=True)
    Path(concat_video).unlink(missing_ok=True)
    if concat_audio:
        Path(concat_audio).unlink(missing_ok=True)
    Path(concat_file).unlink(missing_ok=True)
    if audio_clips:
        Path(audio_concat_file).unlink(missing_ok=True)
    
    print(f"Rendered video: {output_path}")
    return str(output_path)


def generate_thumbnail(
    thumb_image_path: str,
    thumb_text: Dict[str, str],
    output_dir: Path,
    output_name: str = "thumbnail.png"
) -> str:
    """
    Generate thumbnail with overlay text using PIL.
    
    Args:
        thumb_image_path: Background image from thumb prompt
        thumb_text: {main: ≤8 chars, sub: ≤12 chars}
        output_dir: Output directory
        output_name: Output filename
    
    Returns:
        Path to thumbnail
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_name
    
    # Open background image
    img = Image.open(thumb_image_path)
    img = img.resize((THUMB_WIDTH, THUMB_HEIGHT), Image.Resampling.LANCZOS)
    
    draw = ImageDraw.Draw(img)
    
    # Try to load Japanese fonts
    font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansJP-Black.otf",
        "/usr/share/fonts/noto-cjk/NotoSansCJKjp-Black.otf",
        "/usr/share/fonts/truetype/noto/NotoSansJP-Bold.ttf",
        "C:\\Windows\\Fonts\\msgothic.ttc"
    ]
    
    main_font = None
    sub_font = None
    
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                main_font = ImageFont.truetype(fp, 120)
                sub_font = ImageFont.truetype(fp, 64)
                break
            except Exception:
                continue
    
    if main_font is None:
        # Fallback to default
        main_font = ImageFont.load_default()
        sub_font = ImageFont.load_default()
        print("Warning: Using default font (Japanese may not render correctly)")
    
    main_text = thumb_text.get("main", "")
    sub_text = thumb_text.get("sub", "")
    
    # Draw main text (yellow with black stroke)
    main_bbox = draw.textbbox((0, 0), main_text, font=main_font)
    main_w = main_bbox[2] - main_bbox[0]
    main_h = main_bbox[3] - main_bbox[1]
    main_x = (THUMB_WIDTH - main_w) // 2
    main_y = 110
    
    # Black stroke
    for dx in [-10, -5, 0, 5, 10]:
        for dy in [-10, -5, 0, 5, 10]:
            if dx != 0 or dy != 0:
                draw.text((main_x + dx, main_y + dy), main_text, font=main_font, fill="black")
    
    # Yellow fill
    draw.text((main_x, main_y), main_text, font=main_font, fill=(255, 220, 0))
    
    # Draw sub text (white with black stroke)
    sub_bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
    sub_w = sub_bbox[2] - sub_bbox[0]
    sub_h = sub_bbox[3] - sub_bbox[1]
    sub_x = (THUMB_WIDTH - sub_w) // 2
    sub_y = 500
    
    # Black stroke
    for dx in [-8, -4, 0, 4, 8]:
        for dy in [-8, -4, 0, 4, 8]:
            if dx != 0 or dy != 0:
                draw.text((sub_x + dx, sub_y + dy), sub_text, font=sub_font, fill="black")
    
    # White fill
    draw.text((sub_x, sub_y), sub_text, font=sub_font, fill="white")
    
    img.save(output_path)
    print(f"Generated thumbnail: {output_path}")
    return str(output_path)


def generate_description(
    description: str,
    scenes: List[Dict[str, Any]],
    hashtags: List[str],
    output_dir: Path,
    output_name: str = "description_final.txt"
) -> str:
    """
    Generate final description with chapters.
    
    Args:
        description: Base description from metadata
        scenes: Scenes with timing and sections
        hashtags: Hashtag list
        output_dir: Output directory
        output_name: Output filename
    
    Returns:
        Path to description file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_name
    
    lines = [description, "", "【チャプター】"]
    
    for scene in scenes:
        section = scene.get("section", "")
        item_no = scene.get("item_no")
        start = scene.get("start", 0)
        
        timestamp = format_timestamp(start)
        
        if item_no:
            lines.append(f"{timestamp} {section} {item_no}")
        else:
            lines.append(f"{timestamp} {section}")
    
    lines.append("")
    lines.append(" ".join(hashtags))
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"Generated description: {output_path}")
    return str(output_path)
