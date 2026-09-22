"""
Image prompt generation with MASCOT_LOCK and STYLE_LOCK.
"""
from typing import Dict, List, Any
from core.llm import chat_with_json_output
from core.brand import MASCOT_LOCK, STYLE_LOCK


def generate_image_prompts(scenes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate image prompts for each scene's visual field.
    
    Returns dict with:
    - scene_prompts: {scene_id: full_prompt}
    - thumb_prompt: prompt for thumbnail background
    """
    system_prompt = """あなたは画像生成プロンプトエンジニアです。
各シーンの visual 説明を、英語の画像生成プロンプトに変換してください。

重要：
- 文字・ロゴ・テキストは絶対に含めない（NO text, NO letters）
- mascot の表情・ポーズ・物体・構図のみを描写
- シンプルな背景
- 日本語 YouTube エクスプレナー動画スタイル"""

    # Build input for LLM
    scene_inputs = []
    for scene in scenes:
        scene_inputs.append({
            "id": scene["id"],
            "section": scene.get("section", ""),
            "visual": scene.get("visual", "")
        })

    user_prompt = f"""以下の各シーンについて、英語で画像生成プロンプトを作成してください。

シーン一覧：
{chr(10).join([f"- ID {s['id']} ({s['section']}): {s['visual']}" for s in scene_inputs])}

出力 JSON 形式：
{{
  "scene_prompts": {{
    "1": "English prompt for scene 1...",
    "2": "English prompt for scene 2...",
    ...
  }},
  "thumb_prompt": "English prompt for thumbnail background with space at top and bottom for text overlay"
}}

※ 各プロンプトには「NO text, NO letters, NO watermark」を含めてください。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    result = chat_with_json_output(messages, temperature=0.7)
    
    # Apply MASCOT_LOCK and STYLE_LOCK to all prompts
    scene_prompts = result.get("scene_prompts", {})
    thumb_prompt = result.get("thumb_prompt", "")
    
    locked_scene_prompts = {}
    for scene_id, prompt in scene_prompts.items():
        # Append locks
        full_prompt = f"{prompt}. {MASCOT_LOCK}. {STYLE_LOCK}"
        locked_scene_prompts[scene_id] = full_prompt
    
    # Lock thumb prompt too (but allow simpler composition)
    full_thumb_prompt = f"{thumb_prompt}. {MASCOT_LOCK}. {STYLE_LOCK}"
    
    return {
        "scene_prompts": locked_scene_prompts,
        "thumb_prompt": full_thumb_prompt
    }
