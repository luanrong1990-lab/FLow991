"""
Metadata generation: titles, thumbnail text, hashtags, description.
"""
from typing import Dict, Any
from core.llm import chat_with_json_output
from core.brand import DISCLAIMER_JP


def generate_metadata(script: Dict[str, Any], topic: str) -> Dict[str, Any]:
    """
    Generate video metadata from script.
    
    Returns dict with:
    - titles: 3 options (≤40 chars each, can use【】+ year)
    - thumb: {main: ≤8 chars, sub: ≤12 chars}
    - hashtags: 5-8 hashtags with #
    - description: overview + keywords + disclaimer
    """
    system_prompt = """あなたは YouTube のメタデータ最適化専門家です。
日本語の YouTube 動画向けに、クリック率を高めるタイトルとサムネイルテキスト、
SEO を考慮した説明欄を作成してください。

制約：
- title: 40 文字以内、3 パターン作成。【】や年份（2025）を使っても良い
- thumb.main: 8 文字以内（メイン文言、大きく表示）
- thumb.sub: 12 文字以内（サブ文言）
- hashtags: 5-8 個、# を付ける
- description: 概要＋キーワード＋固定の免責事項"""

    # Extract key info from script
    scenes = script.get("scenes", [])
    working_title = script.get("working_title", "")
    
    # Build summary for context
    item_scenes = [s for s in scenes if s.get("section") == "ITEM"]
    items_summary = "\n".join([
        f"- {s.get('item_no')}: {s.get('visual', '')[:50]}"
        for s in item_scenes[:6]
    ])

    user_prompt = f"""トピック：{topic}
作業用タイトル：{working_title}

紹介するアイテム（一部）：
{items_summary}

以下の JSON 形式で出力：
{{
  "titles": [
    "【2025 年最新版】副業 12 選｜月 5 万円から始める方法",
    "サラリーマン必見！知られざる 12 の収入源",
    "【完全保存版】不労所得の作り方 12 パターン"
  ],
  "thumb": {{
    "main": "月 10 万！",
    "sub": "在宅で簡単 12 選"
  }},
  "hashtags": [
    "#副業",
    "#不労所得",
    "#サイドビジネス",
    "#収入アップ",
    "#起業",
    "#パッシブインカム",
    "#日本",
    "#お金"
  ],
  "description": "この動画では、初心者でも始められる副業・ビジネスを 12 個紹介します。...（中略）...\\n\\n{DISCLAIMER_JP}"
}}

※ description には必ず免責事項を含めてください。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    metadata = chat_with_json_output(messages, temperature=0.7)
    
    # Validate lengths
    for i, title in enumerate(metadata.get("titles", [])):
        if len(title) > 40:
            metadata["titles"][i] = title[:40]
    
    thumb = metadata.get("thumb", {})
    if len(thumb.get("main", "")) > 8:
        thumb["main"] = thumb["main"][:8]
    if len(thumb.get("sub", "")) > 12:
        thumb["sub"] = thumb["sub"][:12]
    
    hashtags = metadata.get("hashtags", [])
    if len(hashtags) < 5:
        # Add defaults
        defaults = ["#副業", "#ビジネス", "#収入", "#日本", "#節約"]
        for d in defaults:
            if d not in hashtags and len(hashtags) < 5:
                hashtags.append(d)
    elif len(hashtags) > 8:
        hashtags = hashtags[:8]
    
    metadata["hashtags"] = hashtags
    
    return metadata
