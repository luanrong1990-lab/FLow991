"""
TTS generation with morpheme marks for karaoke subtitles.
Supports edge-tts (default, free) and Google Cloud TTS.
"""
import os
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
import re

from core.brand import CHAR_RATE_CPM


def tokenize_morphemes(text: str) -> List[str]:
    """
    Tokenize Japanese text into morphemes using SudachiPy.
    Falls back to regex if Sudachi fails.
    """
    try:
        from sudachipy import dictionary
        from sudachipy import tokenizer
        
        tok = dictionary.Dictionary().create()
        tokens = [t.surface() for t in tok.tokenize(text)]
        return [t for t in tokens if t.strip()]
    except Exception:
        # Fallback: simple character/word split
        # Split on punctuation, keep punctuation as separate tokens
        result = []
        current = ""
        for char in text:
            if char in ".,!?。、！？…":
                if current:
                    result.append(current)
                    current = ""
                result.append(char)
            else:
                current += char
        if current:
            result.append(current)
        return result


async def tts_edge(
    text: str,
    output_path: Path,
    voice: str = "ja-JP-NaokiNeural"
) -> Dict[str, Any]:
    """
    Generate TTS using edge-tts.
    Returns duration and estimated morpheme marks.
    """
    import edge_tts
    
    # Generate audio
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))
    
    # Get duration using ffprobe
    dur = get_audio_duration(output_path)
    
    # Tokenize and distribute marks proportionally
    morphemes = tokenize_morphemes(text)
    marks = []
    
    if morphemes and dur > 0:
        # Calculate cumulative time for each morpheme
        total_chars = sum(len(m) for m in morphemes)
        current_time = 0.0
        
        for morph in morphemes:
            # Proportional duration based on character count
            morph_dur = (len(morph) / total_chars) * dur if total_chars > 0 else dur / len(morphemes)
            marks.append([morph, round(current_time, 3)])
            current_time += morph_dur
    
    return {
        "path": str(output_path),
        "dur": round(dur, 3),
        "marks": marks
    }


async def tts_gcp(
    text: str,
    output_path: Path,
    voice: str = "ja-JP-Neural2-B"
) -> Dict[str, Any]:
    """
    Generate TTS using Google Cloud Text-to-Speech with SSML marks.
    Returns actual timepoints from API.
    """
    from google.cloud import texttospeech
    
    client = texttospeech.TextToSpeechClient()
    
    # Build SSML with morpheme marks
    morphemes = tokenize_morphemes(text)
    ssml_parts = ['<speak>']
    
    for i, morph in enumerate(morphemes):
        ssml_parts.append(f'<mark name="m{i}"/>')
        # Escape special XML characters
        escaped = morph.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        ssml_parts.append(escaped)
    
    ssml_parts.append('</speak>')
    ssml = "".join(ssml_parts)
    
    synthesis_input = texttospeech.SynthesisInput(ssml=ssml)
    voice_obj = texttospeech.VoiceSelectionParams(
        language_code="ja-JP",
        name=voice,
        ssml_gender=texttospeech.SsmlVoiceGender.MALE
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    
    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice_obj,
        audio_config=audio_config,
        enable_timepointing=True
    )
    
    # Save audio
    with open(output_path, "wb") as f:
        f.write(response.audio_content)
    
    # Get duration
    dur = get_audio_duration(output_path)
    
    # Extract marks from timepoints (GCP returns actual timing)
    marks = []
    for tp in response.timepoints:
        morph_idx = int(tp.mark_name.replace("m", ""))
        if 0 <= morph_idx < len(morphemes):
            marks.append([morphemes[morph_idx], round(tp.time_seconds, 3)])
    
    return {
        "path": str(output_path),
        "dur": round(dur, 3),
        "marks": marks
    }


def get_audio_duration(path: Path) -> float:
    """Get audio duration in seconds using ffprobe."""
    import subprocess
    
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 5.0  # Default fallback


async def generate_tts(
    scenes: List[Dict[str, Any]],
    output_dir: Path,
    provider: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Generate TTS for all scenes.
    
    Args:
        scenes: Scenes with narration text
        output_dir: Directory to save audio files
        provider: 'edge' or 'gcp'
    
    Returns:
        List of {scene_id, path, dur, marks}
    """
    if provider is None:
        provider = os.getenv("TTS_PROVIDER", "edge")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    for scene in scenes:
        scene_id = scene.get("id")
        narration = scene.get("narration", "")
        
        if not narration:
            continue
        
        output_path = output_dir / f"scene_{scene_id}.mp3"
        
        print(f"Generating TTS for scene {scene_id}...")
        
        if provider == "edge":
            result = await tts_edge(narration, output_path)
        elif provider == "gcp":
            result = await tts_gcp(narration, output_path)
        else:
            raise ValueError(f"Unknown TTS provider: {provider}")
        
        result["scene_id"] = scene_id
        results.append(result)
        print(f"TTS done for scene {scene_id}: {result['dur']}s")
    
    return results
