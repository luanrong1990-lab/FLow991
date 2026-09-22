"""
Pipeline orchestrator: coordinates all steps with state management.
"""
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

from core.state import (
    create_project, load_state, save_state, update_step,
    append_topic_used, get_project_dir, STEPS
)
from pipeline.topics import suggest_topics
from pipeline.script_writer import write_script
from pipeline.metadata import generate_metadata
from pipeline.scenes import estimate_timing, align_with_audio
from pipeline.prompts import generate_image_prompts
from pipeline.images import generate_images
from pipeline.tts import generate_tts
from pipeline.subtitles import generate_ass
from pipeline.render import render_video, generate_thumbnail, generate_description


class PipelineOrchestrator:
    """Orchestrate the full video production pipeline."""
    
    def __init__(self, pid: Optional[str] = None):
        """
        Initialize orchestrator.
        
        Args:
            pid: Project ID (create new if None)
        """
        if pid is None:
            self.pid = create_project()
            self.state = load_state(self.pid)
        else:
            self.pid = pid
            self.state = load_state(pid)
            if self.state is None:
                raise ValueError(f"Project {pid} not found")
        
        self.project_dir = get_project_dir(self.pid)
    
    def get_current_step(self) -> str:
        """Get current pipeline step."""
        return self.state.get("step", "init")
    
    def can_proceed_to(self, target_step: str) -> bool:
        """Check if we can proceed to target step."""
        current_idx = STEPS.index(self.get_current_step())
        target_idx = STEPS.index(target_step)
        return target_idx == current_idx + 1
    
    # Step 1: Suggest topics
    def suggest_topics(self) -> list:
        """Generate topic suggestions."""
        topics = suggest_topics()
        self.state["candidates"] = topics
        save_state(self.pid, self.state)
        return topics
    
    # Step 2: Select topic
    def select_topic(self, topic_idx: int) -> Dict[str, Any]:
        """Select a topic from candidates."""
        candidates = self.state.get("candidates", [])
        if not candidates or topic_idx < 0 or topic_idx >= len(candidates):
            raise ValueError("Invalid topic selection")
        
        selected = candidates[topic_idx]
        topic_text = f"{selected['topic']} {selected['angle']}"
        
        self.state["topic"] = selected
        append_topic_used(topic_text)
        update_step(self.pid, "topic")
        
        return selected
    
    # Step 3: Write script
    def write_script(self) -> Dict[str, Any]:
        """Generate script from selected topic."""
        topic_data = self.state.get("topic")
        if not topic_data:
            raise ValueError("No topic selected")
        
        script = write_script(
            topic_data.get("topic", ""),
            topic_data.get("angle", "")
        )
        
        self.state["script"] = script
        self.state["scenes"] = estimate_timing(script)
        update_step(self.pid, "script")
        save_state(self.pid, self.state)
        
        return script
    
    # Step 4: Generate metadata
    def generate_metadata(self) -> Dict[str, Any]:
        """Generate titles, thumbnail text, hashtags, description."""
        script = self.state.get("script")
        topic_data = self.state.get("topic")
        
        if not script or not topic_data:
            raise ValueError("Script or topic missing")
        
        meta = generate_metadata(
            script,
            topic_data.get("topic", "")
        )
        
        self.state["meta"] = meta
        update_step(self.pid, "meta")
        save_state(self.pid, self.state)
        
        return meta
    
    # Step 5: Generate image prompts
    def generate_prompts(self) -> Dict[str, Any]:
        """Generate image prompts for all scenes."""
        scenes = self.state.get("scenes", [])
        
        if not scenes:
            raise ValueError("No scenes available")
        
        prompts = generate_image_prompts(scenes)
        
        self.state["prompts"] = prompts["scene_prompts"]
        self.state["thumb_prompt"] = prompts["thumb_prompt"]
        update_step(self.pid, "prompts")
        save_state(self.pid, self.state)
        
        return prompts
    
    # Step 6: Generate images
    async def generate_images(self, provider: Optional[str] = None) -> Dict[str, str]:
        """Generate images for all scenes."""
        prompts = self.state.get("prompts", {})
        
        if not prompts:
            raise ValueError("No prompts available")
        
        images_dir = self.project_dir / "images"
        images = await generate_images(prompts, images_dir, provider)
        
        self.state["images"] = images
        update_step(self.pid, "images")
        save_state(self.pid, self.state)
        
        return images
    
    # Step 7: Generate TTS
    async def generate_tts(self, provider: Optional[str] = None) -> list:
        """Generate TTS for all scenes."""
        scenes = self.state.get("scenes", [])
        
        if not scenes:
            raise ValueError("No scenes available")
        
        tts_dir = self.project_dir / "tts"
        tts_results = await generate_tts(scenes, tts_dir, provider)
        
        # Align timing with actual audio
        aligned_scenes = align_with_audio(scenes, tts_results)
        self.state["scenes"] = aligned_scenes
        self.state["tts"] = tts_results
        update_step(self.pid, "tts")
        save_state(self.pid, self.state)
        
        return tts_results
    
    # Step 8: Generate subtitles
    def generate_subtitles(self) -> str:
        """Generate .ass subtitle file."""
        scenes = self.state.get("scenes", [])
        tts_results = self.state.get("tts", [])
        
        if not scenes or not tts_results:
            raise ValueError("Scenes or TTS results missing")
        
        subs_dir = self.project_dir / "subs"
        subs_dir.mkdir(parents=True, exist_ok=True)
        ass_path = subs_dir / "subtitles.ass"
        
        generate_ass(scenes, tts_results, ass_path)
        
        self.state["ass"] = str(ass_path)
        update_step(self.pid, "subs")
        save_state(self.pid, self.state)
        
        return str(ass_path)
    
    # Step 9: Render final video
    def render_final(self) -> Dict[str, str]:
        """Render final video, thumbnail, and description."""
        scenes = self.state.get("scenes", [])
        images = self.state.get("images", {})
        tts_results = self.state.get("tts", [])
        ass_path = self.state.get("ass")
        meta = self.state.get("meta", {})
        
        if not all([scenes, images, tts_results, ass_path, meta]):
            raise ValueError("Missing required assets for rendering")
        
        output_dir = self.project_dir / "output"
        
        # Render video
        video_path = render_video(
            scenes, images, tts_results,
            Path(ass_path), output_dir
        )
        
        # Generate thumbnail
        thumb_prompt = self.state.get("thumb_prompt")
        if thumb_prompt:
            # First generate thumb image if using flowkit
            thumb_img_dir = self.project_dir / "thumb"
            from pipeline.images import generate_images as gen_imgs
            import asyncio
            
            # For now, use first scene image as placeholder
            # In production, generate separate thumb image
            first_img = list(images.values())[0] if images else None
            if first_img:
                thumb_path = generate_thumbnail(
                    first_img,
                    meta.get("thumb", {}),
                    output_dir
                )
            else:
                thumb_path = None
        else:
            thumb_path = None
        
        # Generate description
        desc_path = generate_description(
            meta.get("description", ""),
            scenes,
            meta.get("hashtags", []),
            output_dir
        )
        
        self.state["video"] = video_path
        self.state["thumb"] = thumb_path
        self.state["desc"] = desc_path
        update_step(self.pid, "done")
        save_state(self.pid, self.state)
        
        return {
            "video": video_path,
            "thumb": thumb_path,
            "desc": desc_path
        }
