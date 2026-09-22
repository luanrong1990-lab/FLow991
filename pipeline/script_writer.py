"""
Script writer with RULES validation and auto-correction.
"""
import json
from typing import Dict, List, Any, Optional
from core.llm import chat_with_json_output
from core.brand import DISCLAIMER_JP, CHAR_RATE_CPM

# Load rules from file
def load_script_rules() -> str:
    with open("rules/script_rules.md", "r", encoding="utf-8") as f:
        return f.read()


def write_script(topic: str, angle: str) -> Dict[str, Any]:
    """
    Write a complete script following the RULES.
    
    Args:
        topic: Main topic title
        angle: Specific angle/approach
    
    Returns:
        Script dict with working_title and scenes list
    """
    rules = load_script_rules()
    
    system_prompt = f"""あなたは日本の YouTube チャンネル用台本作家です。
以下の RULES を厳守して台本を執筆してください。

{rules}

重要：出力は必ず JSON 形式のみで、markdown のコードブロックは含めないでください。"""

    user_prompt = f"""トピック：{topic}
切り口：{angle}

上記のトピックで、12 個のビジネス/副業を紹介する動画の台本を作成してください。
各 ITEM は 60-90 秒（約 200-280 文字）で、以下の要素を含めてください：
- それは何か
- なぜ収益性があるか
- 必要な資金の目安
- リスク・障壁
- 再現性

出力 JSON 形式：
{{
  "working_title": "作業用タイトル",
  "scenes": [
    {{
      "id": 1,
      "section": "HOOK",
      "item_no": null,
      "visual": "ナレーターまたは mascot が驚いた表情で上を指している",
      "narration": "日本語ナレーション全文",
      "telop": ["短いテキスト 1", "短いテキスト 2"],
      "insert_slot": false
    }},
    ...
  ]
}}

section の値：HOOK, OPENING, ITEM, MIDCHECK, RECAP, OUTRO
item_no: ITEM セクションでは 1-12 の番号、それ以外は null
telop: 各行 13 文字以内、最大 2 行
insert_slot: case study やグラフを挿入すべき場所は true"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    script = chat_with_json_output(messages, temperature=0.7, max_tokens=6000)
    
    # Validate and auto-correct
    errors = validate_script(script)
    if errors:
        # Try to fix once
        script = fix_script(script, errors, rules)
        errors = validate_script(script)
        if errors:
            raise ValueError(f"Script validation failed after correction: {errors}")
    
    return script


def validate_script(script: Dict[str, Any]) -> List[str]:
    """
    Validate script against RULES.
    
    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    scenes = script.get("scenes", [])
    
    if not scenes:
        errors.append("No scenes found in script")
        return errors
    
    # Check required sections exist
    sections_found = set(s.get("section") for s in scenes)
    required_sections = {"HOOK", "OPENING", "OUTRO"}
    missing = required_sections - sections_found
    if missing:
        errors.append(f"Missing required sections: {missing}")
    
    # Check each scene
    for i, scene in enumerate(scenes):
        scene_id = scene.get("id", i+1)
        section = scene.get("section")
        narration = scene.get("narration", "")
        telop = scene.get("telop", [])
        
        # Narration length check for ITEM sections
        if section == "ITEM":
            char_count = len(narration)
            if char_count < 120 or char_count > 350:
                errors.append(
                    f"Scene {scene_id} (ITEM): narration has {char_count} chars "
                    f"(should be 120-350)"
                )
        
        # Telop length check
        for j, line in enumerate(telop):
            if len(line) > 13:
                errors.append(
                    f"Scene {scene_id} telop line {j+1}: '{line}' has {len(line)} chars "
                    f"(max 13)"
                )
        
        # Check disclaimer in OPENING
        if section == "OPENING":
            if DISCLAIMER_JP not in narration:
                errors.append("OPENING scene missing required disclaimer")
    
    # Check for prohibited profit guarantees
    full_text = json.dumps(script, ensure_ascii=False)
    prohibited_phrases = ["必ず儲かる", "絶対に成功", "保証された利益", "100% 確実"]
    for phrase in prohibited_phrases:
        if phrase in full_text:
            errors.append(f"Prohibited phrase found: '{phrase}'")
    
    return errors


def fix_script(script: Dict[str, Any], errors: List[str], rules: str) -> Dict[str, Any]:
    """
    Request LLM to fix identified errors.
    """
    system_prompt = f"""あなたは校正係です。指摘されたエラーを修正してください。
RULES は以下に従います：

{rules}"""

    user_prompt = f"""以下の台本にエラーがあります。修正版を JSON で返してください。

元台本：
{json.dumps(script, ensure_ascii=False)}

エラー一覧：
{chr(10).join(errors)}

修正点：
- 各 ITEM のナレーションを 120-350 文字に調整
- telop を 13 文字以内に短縮
- DISCLAIMER を OPENING に追加
- 禁止表現を削除

出力は JSON 形式のみでお願いします。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    return chat_with_json_output(messages, temperature=0.5, max_tokens=6000)
