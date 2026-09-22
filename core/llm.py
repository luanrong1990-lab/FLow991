"""
LLM client wrapper supporting OpenAI-compatible APIs.
"""
import os
import json
from typing import Any, Dict, List, Optional
from openai import OpenAI

def get_llm_client() -> OpenAI:
    """Initialize LLM client from environment variables."""
    api_key = os.getenv("LLM_API_KEY", "sk-placeholder")
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    
    return OpenAI(api_key=api_key, base_url=base_url)


def chat_completion(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    response_format: Optional[Dict[str, str]] = None
) -> str:
    """
    Send chat completion request to LLM.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        model: Model name (override env)
        temperature: Sampling temperature
        max_tokens: Max tokens in response
        response_format: e.g. {"type": "json_object"}
    
    Returns:
        Response text content
    """
    client = get_llm_client()
    if model is None:
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    if response_format:
        kwargs["response_format"] = response_format
    
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def chat_with_json_output(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096
) -> Dict[str, Any]:
    """
    Send chat completion requesting JSON output.
    Retries up to 3 times if JSON parsing fails.
    """
    for attempt in range(3):
        try:
            text = chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )
            # Strip markdown code blocks if present
            if text.startswith("```"):
                lines = text.split("\n")
                if lines[0].startswith("```json"):
                    lines = lines[1:]
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)
            return json.loads(text)
        except json.JSONDecodeError as e:
            if attempt == 2:
                raise ValueError(f"LLM returned invalid JSON after 3 attempts: {e}")
            # Retry with error feedback
            messages.append({
                "role": "user",
                "content": f"JSON parsing failed: {e}. Please return valid JSON only."
            })
    
    raise ValueError("Failed to get valid JSON from LLM")
