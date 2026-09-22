"""
Image generation via FlowKit or Gemini fallback.
"""
import os
import base64
from pathlib import Path
from typing import Dict, List, Any, Optional
import asyncio

from pipeline.flowkit_bridge import get_bridge, load_mascot_ref


async def generate_images_flowkit(
    prompts: Dict[str, str],
    output_dir: Path
) -> Dict[str, str]:
    """
    Generate images using FlowKit bridge (Google Flow).
    
    Args:
        prompts: {scene_id: prompt}
        output_dir: Directory to save images
    
    Returns:
        {scene_id: image_path}
    """
    bridge = get_bridge()
    
    # Load mascot reference
    try:
        ref_base64 = load_mascot_ref()
    except FileNotFoundError as e:
        raise RuntimeError(str(e))
    
    results = {}
    
    for scene_id, prompt in prompts.items():
        print(f"Generating image for scene {scene_id}...")
        
        try:
            images = await bridge.send_job(
                prompt=prompt,
                ref_base64=ref_base64,
                n=1,
                timeout=180.0
            )
            
            if images:
                # Save first image
                img_data = base64.b64decode(images[0])
                img_path = output_dir / f"scene_{scene_id}.png"
                with open(img_path, "wb") as f:
                    f.write(img_data)
                results[str(scene_id)] = str(img_path)
                print(f"Saved: {img_path}")
            else:
                print(f"No image returned for scene {scene_id}")
                
        except TimeoutError as e:
            print(f"Timeout for scene {scene_id}: {e}")
            results[str(scene_id)] = None
        except Exception as e:
            print(f"Error for scene {scene_id}: {e}")
            results[str(scene_id)] = None
    
    return results


def generate_images_gemini(
    prompts: Dict[str, str],
    output_dir: Path
) -> Dict[str, str]:
    """
    Fallback: Generate images using Gemini 2.5 Flash Image.
    
    Requires: GOOGLE_API_KEY env var, google-genai package
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set for Gemini fallback")
    
    from google import genai
    from google.genai import types
    
    client = genai.Client(api_key=api_key)
    
    # Load mascot reference as image
    ref_path = Path(__file__).parent.parent / "assets" / "mascot_ref.png"
    if not ref_path.exists():
        raise FileNotFoundError("Mascot reference sheet not found")
    
    results = {}
    
    for scene_id, prompt in prompts.items():
        print(f"Gemini generating image for scene {scene_id}...")
        
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=[
                    {"mime_type": "image/png", "data": open(ref_path, "rb").read()},
                    prompt
                ]
            )
            
            # Extract image from response
            if response.candidates and response.candidates[0].content.parts:
                img_part = response.candidates[0].content.parts[0]
                if hasattr(img_part, "inline_data"):
                    img_data = img_part.inline_data.data
                    
                    img_path = output_dir / f"scene_{scene_id}.png"
                    with open(img_path, "wb") as f:
                        f.write(img_data)
                    results[str(scene_id)] = str(img_path)
                    print(f"Saved: {img_path}")
                    
        except Exception as e:
            print(f"Error for scene {scene_id}: {e}")
            results[str(scene_id)] = None
    
    return results


async def generate_images(
    prompts: Dict[str, str],
    output_dir: Path,
    provider: Optional[str] = None
) -> Dict[str, str]:
    """
    Main entry point for image generation.
    
    Args:
        prompts: {scene_id: prompt}
        output_dir: Directory to save images
        provider: 'flowkit' or 'gemini' (auto-detect from env if None)
    
    Returns:
        {scene_id: image_path}
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if provider is None:
        provider = os.getenv("IMG_PROVIDER", "flowkit")
    
    if provider == "flowkit":
        return await generate_images_flowkit(prompts, output_dir)
    elif provider == "gemini":
        return generate_images_gemini(prompts, output_dir)
    else:
        raise ValueError(f"Unknown provider: {provider}")
