"""
Scene timing estimation and alignment.
"""
from typing import Dict, List, Any
from core.brand import CHAR_RATE_CPM


def estimate_timing(script: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Estimate scene timing from narration length.
    
    Formula: dur = len(narration) / 320 * 60 + 1.2 (padding)
    
    Returns scenes with start, end, dur fields added.
    """
    scenes = script.get("scenes", [])
    timed_scenes = []
    current_time = 0.0
    
    for scene in scenes:
        narration = scene.get("narration", "")
        char_count = len(narration)
        
        # Duration estimate
        dur = (char_count / CHAR_RATE_CPM) * 60 + 1.2
        dur = round(dur, 2)
        
        start = round(current_time, 2)
        end = round(start + dur, 2)
        
        timed_scene = {**scene, "start": start, "end": end, "dur": dur}
        timed_scenes.append(timed_scene)
        
        current_time = end
    
    return timed_scenes


def align_with_audio(scenes: List[Dict[str, Any]], tts_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Align scene timing with actual audio durations from TTS.
    
    Args:
        scenes: Scenes with estimated timing
        tts_results: TTS results with actual durations per scene
    
    Returns:
        Updated scenes with real timing
    """
    # Build lookup: scene_id -> tts result
    tts_lookup = {t["scene_id"]: t for t in tts_results}
    
    aligned_scenes = []
    current_time = 0.0
    
    for scene in scenes:
        scene_id = scene.get("id")
        tts_data = tts_lookup.get(scene_id, {})
        
        # Use actual audio duration if available
        actual_dur = tts_data.get("dur", scene.get("dur", 5.0))
        
        start = round(current_time, 2)
        end = round(start + actual_dur, 2)
        
        aligned_scene = {**scene, "start": start, "end": end, "dur": actual_dur}
        aligned_scenes.append(aligned_scene)
        
        current_time = end
    
    return aligned_scenes


def format_timestamp(seconds: float) -> str:
    """Format seconds as mm:ss for chapters."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"
