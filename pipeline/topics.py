"""
Topic suggestion with deduplication using Jaccard similarity on char-bigrams.
"""
import unicodedata
from typing import List, Dict, Set, Tuple
from core.llm import chat_with_json_output
from core.state import get_topics_used

# Niche categories for topic generation
NICHE_CATEGORIES = [
    "副業（サイドビジネス）",
    "低資本起業・スモールビジネス",
    "不労所得・パッシブインカム",
    "円安・インフレ対策の資産形成",
    "ローカルビジネス・地域密着型",
    "創業助成金・補助金活用"
]


def normalize_text(text: str) -> str:
    """Normalize text: NFKC + lowercase + remove spaces."""
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    text = text.replace(" ", "")
    return text


def extract_char_bigrams(text: str) -> Set[str]:
    """Extract character bigrams from normalized text."""
    normalized = normalize_text(text)
    bigrams = set()
    for i in range(len(normalized) - 1):
        bigrams.add(normalized[i:i+2])
    return bigrams


def jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    """Calculate Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 1.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def is_duplicate(candidate: str, existing: List[str], threshold: float = 0.55) -> bool:
    """
    Check if candidate is duplicate of any existing topic.
    Returns True if similar to any existing (Jaccard > threshold).
    """
    candidate_bigrams = extract_char_bigrams(candidate)
    for existing_topic in existing:
        existing_bigrams = extract_char_bigrams(existing_topic)
        sim = jaccard_similarity(candidate_bigrams, existing_bigrams)
        if sim > threshold:
            return True
    return False


def suggest_topics(force_new: bool = False) -> List[Dict[str, str]]:
    """
    Generate 18 candidate topics, deduplicate against history and within batch,
    return first 6 unique ones.
    
    Args:
        force_new: If True, regenerate even if we have recent suggestions
    
    Returns:
        List of 6 unique topic dicts with {topic, angle}
    """
    used_topics = get_topics_used()
    
    # Build prompt for LLM
    system_prompt = """あなたは日本の YouTube チャンネル運営者です。
以下のニッチで、視聴者が興味を持つトピックを提案してください：
- 副業（サイドビジネス）
- 低資本起業・スモールビジネス
- 不労所得・パッシブインカム
- 円安・インフレ対策の資産形成
- ローカルビジネス・地域密着型
- 創業助成金・補助金活用

各トピックは具体的な「angle」（切り口）を含めてください。"""

    user_prompt = f"""18 個の候補を JSON 形式で返してください。
重複しない多様なトピックにしてください。

出力形式：
{{
  "candidates": [
    {{"topic": "トピック名", "angle": "具体的な切り口"}},
    ...
  ]
}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    response = chat_with_json_output(messages, temperature=0.9)
    candidates = response.get("candidates", [])
    
    # Deduplicate
    unique_topics = []
    seen_in_batch = []
    
    for candidate in candidates:
        topic_text = f"{candidate['topic']} {candidate['angle']}"
        
        # Check against history
        if is_duplicate(topic_text, used_topics):
            continue
        
        # Check against already selected in this batch
        if is_duplicate(topic_text, seen_in_batch):
            continue
        
        unique_topics.append(candidate)
        seen_in_batch.append(topic_text)
        
        if len(unique_topics) >= 6:
            break
    
    # If not enough unique topics, generate more
    while len(unique_topics) < 6 and len(candidates) < 30:
        # Request more diverse topics
        user_prompt = f"""さらに異なる角度から 12 個の候補を追加してください。
既に以下のトピックが選ばれています：
{[t['topic'] for t in unique_topics]}

これらと重複しない新しいトピックを提案してください。"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = chat_with_json_output(messages, temperature=1.0)
        more_candidates = response.get("candidates", [])
        candidates.extend(more_candidates)
        
        for candidate in more_candidates:
            topic_text = f"{candidate['topic']} {candidate['angle']}"
            
            if is_duplicate(topic_text, used_topics):
                continue
            
            if is_duplicate(topic_text, seen_in_batch):
                continue
            
            unique_topics.append(candidate)
            seen_in_batch.append(topic_text)
            
            if len(unique_topics) >= 6:
                break
        
        if len(more_candidates) == 0:
            break
    
    return unique_topics[:6]
