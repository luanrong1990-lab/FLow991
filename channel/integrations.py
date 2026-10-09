"""Small integration helpers shared by the UI and production pipeline."""
from pathlib import Path
import os
import tempfile
import uuid

import requests


def _base(url):
    return str(url or "").strip().rstrip("/")


def discover_flowkit(url="http://127.0.0.1:8100"):
    """Return health plus the Google Flow UUID currently used by FlowKit."""
    base = _base(url)
    client = requests.Session()
    health_response = client.get(base + "/health", timeout=5)
    health_response.raise_for_status()
    health = health_response.json()

    active = {}
    active_error = None
    try:
        response = client.get(base + "/api/active-project", timeout=5)
        response.raise_for_status()
        active = response.json()
    except (requests.RequestException, ValueError) as exc:
        active_error = str(exc)

    status = {}
    try:
        response = client.get(base + "/api/flow/status", timeout=5)
        response.raise_for_status()
        status = response.json()
    except (requests.RequestException, ValueError):
        pass

    active_project_id = active.get("project_id")
    pinned_project_id = status.get("flow_project_id")
    project_id = active_project_id or pinned_project_id
    if project_id:
        try:
            project_id = str(uuid.UUID(str(project_id)))
        except ValueError as exc:
            raise ValueError("FlowKit trả về project ID không phải UUID Google Flow.") from exc

    return {
        "base_url": base,
        "extension_connected": bool(health.get("extension_connected")),
        "project_id": project_id,
        "project_name": active.get("project_name"),
        "video_id": active.get("video_id"),
        "source": active.get("source") if active_project_id else ("pinned_flow_project" if pinned_project_id else "none"),
        "transport": status.get("transport"),
        "active_project_error": active_error,
    }


def resolve_flow_project(url, requested=""):
    """Prefer an explicit UUID; otherwise use FlowKit's active/pinned project."""
    requested = str(requested or "").strip()
    if requested:
        try:
            project_id = str(uuid.UUID(requested))
        except ValueError as exc:
            raise ValueError("UUID Flow đã nhập không hợp lệ.") from exc
        info = discover_flowkit(url)
        info["project_id"] = project_id
        info["source"] = "manual"
        return info
    info = discover_flowkit(url)
    if not info["project_id"]:
        raise ValueError("FlowKit chưa có project đang hoạt động. Hãy chọn/tạo project trong FlowKit trước.")
    return info


def voicevox_info(url="http://127.0.0.1:50021"):
    base = _base(url)
    client = requests.Session()
    version_response = client.get(base + "/version", timeout=5)
    version_response.raise_for_status()
    speakers_response = client.get(base + "/speakers", timeout=15)
    speakers_response.raise_for_status()
    speakers = []
    for person in speakers_response.json():
        for style in person.get("styles", []):
            if style.get("type", "talk") not in ("talk", None):
                continue
            speakers.append({
                "id": int(style["id"]),
                "speaker": str(person.get("name", "")),
                "style": str(style.get("name", "")),
                "label": f"{person.get('name', '')} · {style.get('name', '')}  (ID {style['id']})",
            })
    speakers.sort(key=lambda item: (item["speaker"], item["id"]))
    return {"base_url": base, "version": str(version_response.json()), "speakers": speakers}


def synthesize_voicevox_preview(url, speaker_id, destination=None, speed=0.95):
    """Create a short Japanese WAV using the exact API used by production."""
    base = _base(url)
    speaker_id = int(speaker_id)
    text = "こんにちは。静かに稼ぐ研究室です。落ち着いて、お金の話を見ていきましょう。"
    client = requests.Session()
    query_response = client.post(base + "/audio_query", params={"text": text, "speaker": speaker_id}, timeout=30)
    query_response.raise_for_status()
    query = query_response.json()
    query.update(speedScale=float(speed), outputSamplingRate=24000, outputStereo=False)
    audio_response = client.post(base + "/synthesis", params={"speaker": speaker_id}, json=query, timeout=180)
    audio_response.raise_for_status()
    if destination is None:
        destination = Path(tempfile.gettempdir()) / "vqveo3pro_voicevox_preview.wav"
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".pending.wav")
    temporary.write_bytes(audio_response.content)
    os.replace(temporary, destination)
    return str(destination)
