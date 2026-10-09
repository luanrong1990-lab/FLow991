"""Narration timing, real chapters and Japanese subtitles from synthesized sentences."""
import hashlib
import json
from pathlib import Path
import re
import wave
import requests
from channel.rules import sentences


def timestamp(seconds, srt=False):
    ticks = round(seconds * (1000 if srt else 100))
    unit = 1000 if srt else 100
    total, fraction = divmod(ticks, unit)
    minutes, second = divmod(total, 60)
    hour, minute = divmod(minutes, 60)
    return (f"{hour:02}:{minute:02}:{second:02},{fraction:03}" if srt else
            f"{hour}:{minute:02}:{second:02}.{fraction:02}")


def subtitle_files(folder, cues, profile):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    # Subtitles use exact sentence WAV boundaries; not word-alignment estimates.
    ass = ["[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n[V4+ Styles]\n",
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n",
           f"Style: Japanese,{profile['font_family']},48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,180,180,50,1\n\n[Events]\n",
           "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"]
    srt = []
    for index, cue in enumerate(cues, 1):
        text = cue["text"].replace("\r", " ").replace("\n", " ")
        wrapped = "\n".join(text[i:i+26] for i in range(0, len(text), 26))
        safe = wrapped.replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\n", r"\N")
        ass.append(f"Dialogue: 0,{timestamp(cue['start'])},{timestamp(cue['end'])},Japanese,,0,0,0,,{safe}\n")
        srt.append(f"{index}\n{timestamp(cue['start'], True)} --> {timestamp(cue['end'], True)}\n{wrapped}\n\n")
    ass_path, srt_path = folder / "subtitles.ass", folder / "subs_ja.srt"
    ass_path.write_text("".join(ass), encoding="utf-8")
    srt_path.write_text("".join(srt), encoding="utf-8")
    return str(ass_path), str(srt_path)


def chapters(schedule):
    result = []
    for entry in schedule:
        if entry.get("bumper") or entry["type"] in ("hook", "recap", "outro"):
            seconds = int(entry["start"])
            h, remainder = divmod(seconds, 3600)
            m, s = divmod(remainder, 60)
            time = f"{h}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"
            title = "オープニング" if entry["type"] == "hook" else ("まとめ" if entry["type"] == "recap" else entry["telop"])
            result.append(f"{time} {title}")
    return result


def synthesize_episode(scenes, folder, profile, assets, progress, cancelled):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    url = assets.get("voicevox_url", "http://127.0.0.1:50021").rstrip("/")
    speaker = int(assets.get("speaker", 3))
    client = requests.Session()
    response = client.get(url + "/speakers", timeout=10); response.raise_for_status()
    voice = next(((person["name"], style["name"]) for person in response.json() for style in person["styles"] if style["id"] == speaker), None)
    if voice is None:
        raise ValueError(f"VOICEVOX không có speaker ID {speaker}.")
    credit = f"音声：VOICEVOX：{voice[0]}（{voice[1]}）"
    cues, schedule, frame_count = [], [], 0
    rate = 24000
    merged = folder / "merged.pending.wav"
    with wave.open(str(merged), "wb") as writer:
        writer.setnchannels(1); writer.setsampwidth(2); writer.setframerate(rate)
        for sc in scenes:
            if cancelled():
                raise InterruptedError("Đã dừng tạo giọng đọc; phần đã tạo được giữ trong cache.")
            if sc["type"] == "item":
                duration = profile["bumper_seconds"]
                schedule.append({**sc, "bumper": True, "start": frame_count/rate, "duration": duration})
                sting = Path(__file__).resolve().parent / "assets/audio/chapter_sting.wav"
                bumper_frames = round(duration*rate)
                pcm = b""
                if sting.exists():
                    with wave.open(str(sting), "rb") as reader:
                        if (reader.getnchannels(), reader.getsampwidth(), reader.getframerate()) != (1, 2, rate):
                            raise ValueError("Sting cần WAV PCM 16-bit mono 24kHz.")
                        pcm = reader.readframes(bumper_frames)
                writer.writeframes(pcm.ljust(bumper_frames*2, b"\0")); frame_count += bumper_frames
            start = frame_count/rate
            progress(f"VOICEVOX · {sc['id']}")
            for text in sentences(sc["vo"]):
                if cancelled():
                    raise InterruptedError("Đã dừng tạo giọng đọc.")
                key = hashlib.sha256(json.dumps([url, speaker, profile["speed"], text], ensure_ascii=False).encode()).hexdigest()
                path = folder / (key + ".wav")
                if not path.exists():
                    query = client.post(url + "/audio_query", params={"text": text, "speaker": speaker}, timeout=30)
                    query.raise_for_status()
                    payload = query.json()
                    payload.update(speedScale=profile["speed"], outputSamplingRate=rate, outputStereo=False)
                    audio = client.post(url + "/synthesis", params={"speaker": speaker}, json=payload, timeout=180)
                    audio.raise_for_status()
                    temp = path.with_suffix(".pending.wav"); temp.write_bytes(audio.content)
                    with wave.open(str(temp), "rb") as reader:
                        if reader.getnchannels() != 1 or reader.getsampwidth() != 2 or reader.getframerate() != rate or not reader.getnframes():
                            raise ValueError("VOICEVOX trả về WAV không đúng định dạng.")
                    temp.replace(path)
                with wave.open(str(path), "rb") as reader:
                    frames = reader.getnframes(); pcm = reader.readframes(frames)
                begin = frame_count/rate
                writer.writeframes(pcm); frame_count += frames
                cues.append({"scene_id": sc["id"], "text": text, "start": begin, "end": frame_count/rate})
            schedule.append({**sc, "bumper": False, "start": start, "end": frame_count/rate, "duration": frame_count/rate-start})
    final = folder / "merged.wav"; merged.replace(final)
    return {"audio_path": str(final), "cues": cues, "schedule": schedule, "voice_credit": credit,
            "duration": frame_count/rate, "chapters": chapters(schedule)}
