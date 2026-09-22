"""
State management for projects: save/resume pipeline state.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "data"
PROJECTS_DIR = DATA_DIR / "projects"
TOPICS_USED_FILE = DATA_DIR / "topics_used.json"

# Enum steps
STEPS = ["init", "topic", "script", "meta", "prompts", "images", "tts", "subs", "done"]


def ensure_dirs():
    """Create data directories if not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def get_topics_used() -> list:
    """Load list of used topics for deduplication."""
    ensure_dirs()
    if not TOPICS_USED_FILE.exists():
        return []
    with open(TOPICS_USED_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def append_topic_used(topic: str):
    """Append a topic to used list."""
    ensure_dirs()
    topics = get_topics_used()
    topics.append(topic)
    with open(TOPICS_USED_FILE, "w", encoding="utf-8") as f:
        json.dump(topics, f, ensure_ascii=False, indent=2)


def create_project() -> str:
    """Create a new project and return its ID."""
    ensure_dirs()
    pid = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_dir = PROJECTS_DIR / pid
    project_dir.mkdir(parents=True, exist_ok=True)
    
    state = {
        "pid": pid,
        "step": "init",
        "created_at": datetime.now().isoformat(),
        "topic": None,
        "script": None,
        "meta": None,
        "scenes": None,
        "prompts": None,
        "thumb_prompt": None,
        "images": {},
        "tts": None,
        "ass": None,
        "video": None,
        "thumb": None,
        "desc": None
    }
    save_state(pid, state)
    return pid


def get_project_dir(pid: str) -> Path:
    """Get project directory path."""
    return PROJECTS_DIR / pid


def load_state(pid: str) -> Optional[Dict[str, Any]]:
    """Load project state from disk."""
    state_file = get_project_dir(pid) / "state.json"
    if not state_file.exists():
        return None
    with open(state_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(pid: str, state: Dict[str, Any]):
    """Save project state to disk."""
    ensure_dirs()
    project_dir = get_project_dir(pid)
    project_dir.mkdir(parents=True, exist_ok=True)
    state_file = project_dir / "state.json"
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def update_step(pid: str, step: str):
    """Update current step in project state."""
    state = load_state(pid)
    if state is None:
        raise ValueError(f"Project {pid} not found")
    if step not in STEPS:
        raise ValueError(f"Invalid step: {step}")
    state["step"] = step
    save_state(pid, state)


def list_projects() -> list:
    """List all existing projects."""
    ensure_dirs()
    projects = []
    for p in sorted(PROJECTS_DIR.iterdir(), reverse=True):
        if p.is_dir():
            state_file = p / "state.json"
            if state_file.exists():
                with open(state_file, "r", encoding="utf-8") as f:
                    projects.append(json.load(f))
    return projects
