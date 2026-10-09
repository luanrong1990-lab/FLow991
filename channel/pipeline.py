"""Resumable episode production used by the native desktop channel panel."""
import copy
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import shutil
import threading

import requests
from PIL import Image

from channel.rules import (profile_snapshot, system_prompt, image_prompt, scene_issues,
                           seo_issues, thumb_issues)
from utils.json_store import write_json_atomic

STAGES = ("topics", "script", "voice", "images", "thumbnails", "seo", "render")
DEPENDENTS = {
    "topics": ("script", "voice", "images", "thumbnails", "seo", "render"),
    "script": ("voice", "images", "thumbnails", "seo", "render"),
    "voice": ("seo", "render"), "images": ("render",), "thumbnails": ("render",), "seo": ("render",), "render": (),
}


def parse_json(text):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("AI phải trả về JSON object.")
    return value


class Episode:
    def __init__(self, folder):
        self.folder = Path(folder).resolve()
        self.path = self.folder / "episode.json"
        self.state = json.loads(self.path.read_text(encoding="utf-8"))
        if self.state.get("schema_version") != 1:
            raise ValueError("Phiên bản episode chưa được hỗ trợ.")

    @classmethod
    def create(cls, root, name, pillar, brief, sources, assets):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", name):
            raise ValueError("Mã tập chỉ gồm chữ Latin, số, dấu - hoặc _, tối đa 64 ký tự.")
        profile = profile_snapshot()
        if pillar not in profile["pillars"]:
            raise ValueError("Trụ cột không hợp lệ.")
        folder = Path(root).resolve() / name
        folder.mkdir(parents=True, exist_ok=False)
        write_json_atomic(folder / "episode.json", {
            "schema_version": 1, "id": name, "created_at": date.today().isoformat(),
            "pillar": pillar, "style_version": profile["style_version"], "palette": profile["palette"],
            "profile": profile, "brief": brief, "sources": sources, "assets": assets,
            "stages": {}, "scenes": [], "research_reviewed": False,
            "upload": {"status": "manual", "ai_disclosure_review_required": True},
        })
        return cls(folder)

    @property
    def profile(self):
        return self.state["profile"]

    def save(self):
        write_json_atomic(self.path, self.state)

    def freeze_brand_assets(self):
        """Pin content-addressed brand files so later channel edits cannot alter this episode."""
        assets = self.state["assets"]
        if self.state.get("asset_sources") == assets and self.state.get("pinned_assets"):
            return self.state["pinned_assets"]
        fingerprints = {}
        pinned = dict(assets)
        for key in ("font", "bgm"):
            if not assets.get(key):
                continue
            source = Path(assets[key])
            if not source.is_file():
                raise ValueError(f"Không tìm thấy tài sản {key}: {source}")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            dest = self.folder / "brand_assets" / digest[:16] / source.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists(): shutil.copyfile(source, dest)
            pinned[key] = str(dest); fingerprints[key] = digest
        if assets.get("mascot_dir"):
            paths = [Path(assets["mascot_dir"]) / f"mascot_{pose}.png" for pose in self.profile["poses"]]
            if any(not path.is_file() for path in paths):
                raise ValueError("Bộ mascot phải đủ 5 pose PNG cố định.")
            digest = hashlib.sha256(b"".join(p.read_bytes() for p in paths)).hexdigest()
            dest = self.folder / "brand_assets" / digest[:16]; dest.mkdir(parents=True, exist_ok=True)
            for source in paths:
                if not (dest/source.name).exists(): shutil.copyfile(source, dest/source.name)
            pinned["mascot_dir"] = str(dest); fingerprints["mascot"] = digest
        self.state["pinned_assets"] = pinned
        self.state["asset_sources"] = dict(assets)
        self.state["asset_fingerprints"] = fingerprints
        self.save()
        return pinned

    def invalidate(self, stage):
        for dependent in DEPENDENTS[stage]:
            self.state["stages"].pop(dependent, None)
        if stage in ("topics", "script"):
            self.state["research_reviewed"] = False

    def require(self, *stages):
        missing = [s for s in stages if self.state["stages"].get(s) != "done"]
        if missing:
            raise ValueError("Hoàn thành trước: " + ", ".join(missing))

    def save_script(self, scenes):
        errors = scene_issues(scenes, self.profile)
        if errors:
            raise ValueError("\n".join(errors))
        self.invalidate("script")
        self.state["scenes"] = copy.deepcopy(scenes)
        self.state.pop("script_candidate", None)
        self.state.pop("voice_judgement", None)
        self.state.pop("last_error", None)
        self.state["stages"]["script"] = "done"
        self.save()


class ChannelPipeline:
    def __init__(self, episode, ai=None, progress=None, stop=None):
        self.episode = episode
        self.ai = ai
        self.progress = progress or (lambda text: None)
        self.stop = stop or threading.Event()

    @property
    def state(self):
        return self.episode.state

    @property
    def profile(self):
        return self.episode.profile

    def check_stop(self):
        if self.stop.is_set():
            raise InterruptedError("Đã dừng. Có thể chạy lại bước này.")

    def ask(self, task, context):
        self.check_stop()
        if self.ai is None:
            from ai.gemini_provider import GeminiProvider
            self.ai = GeminiProvider()
        return parse_json(self.ai.generate(system_prompt(self.profile) + "\n" + task,
                                         json.dumps(context, ensure_ascii=False)))

    def run(self, stage):
        if stage not in STAGES:
            raise ValueError("Bước không hợp lệ")
        self.check_stop()
        self.episode.invalidate(stage)
        self.state["stages"][stage] = "running"
        self.episode.save()
        try:
            getattr(self, "stage_" + stage)()
            self.check_stop()
            self.state["stages"][stage] = "done"
            self.state.pop("last_error", None)
            self.episode.save()
            self.progress(f"Hoàn tất: {stage}")
        except Exception as exc:
            self.state["stages"][stage] = "stopped" if isinstance(exc, InterruptedError) else "failed"
            self.state["last_error"] = str(exc)
            self.episode.save()
            raise

    def stage_topics(self):
        context = {k: self.state[k] for k in ("pillar", "brief", "sources")}
        context["today"] = date.today().isoformat()
        task = ("IDEATE: đề xuất 5 chủ đề trong trụ cột đã chọn, góc tiếp cận khác nhau. "
                "Xuất {topics:[{title_seed,angle,keyword,thumb_text:[dòng1,dòng2],items:[{name_ja,why_ja,risk_ja}],needs_research:[...]}]}. "
                "Mỗi chủ đề có 5–12 items. thumb_text đúng BIBLE. needs_research ghi rõ dữ kiện cần kiểm chứng. "
                "Không gọi các ý tưởng chưa kiểm chứng là nghiên cứu đã hoàn thành.")
        response = self.ask(task, context)
        topics = response.get("topics")
        if not isinstance(topics, list) or len(topics) != 5:
            raise ValueError("AI phải đề xuất đúng 5 chủ đề.")
        for topic in topics:
            if not isinstance(topic, dict) or not all(isinstance(topic.get(k), str) and topic[k].strip() for k in ("title_seed", "angle", "keyword")):
                raise ValueError("Chủ đề thiếu tiêu đề, góc tiếp cận hoặc từ khóa.")
            if not isinstance(topic.get("items"), list) or not 5 <= len(topic["items"]) <= 12:
                raise ValueError("Chủ đề cần 5–12 mục.")
            errors = thumb_issues(topic.get("thumb_text"), self.profile)
            if errors:
                raise ValueError("\n".join(errors))
        self.state["topics"] = topics
        self.state["selected_topic"] = 0
        self.state["thumb_text"] = topics[0]["thumb_text"]

    def topic(self):
        self.episode.require("topics")
        return self.state["topics"][self.state.get("selected_topic", 0)]

    def stage_script(self):
        topic = self.topic()
        context = {"topic": topic, "sources": self.state["sources"], "brief": self.state["brief"]}
        self.progress("Kịch bản · lập cấu trúc")
        skeleton = self.ask(
            "DRAFT: Xuất {scenes:[{id,type,number,purpose,key_points,numbers,telop,emotion,visual_prompt}]}. "
            "ID SC01... Loại hook,intro,item,mid,recap,outro. Một item cho mỗi mục, checkpoint mid ở giữa. "
            "Hook khoảng 40 giây, mỗi item 60–75 giây. Visual_prompt tiếng Anh: chỉ nền và vật thể, "
            "không mascot, không người, không chữ. Giữ số liệu nguồn; thiếu nguồn dùng định tính.", context)
        draft = skeleton.get("scenes")
        if not isinstance(draft, list) or not 6 <= len(draft) <= 40:
            raise ValueError("Khung kịch bản phải có 6–40 cảnh.")
        written = []
        # Small batches keep long episodes inside the provider output limit.
        for offset in range(0, len(draft), 3):
            self.progress(f"Kịch bản · viết cảnh {offset+1}–{min(offset+3, len(draft))}")
            response = self.ask(
                "WRITE: Xuất {scenes:[{id,type,number,telop,emotion,visual_prompt,vo}]}, "
                "giữ nguyên ID và thứ tự batch. Viết đủ nhịp và thời lượng BIBLE bằng tiếng Nhật tự nhiên. "
                "Hook đúng 1 câu hỏi + teaser số. Intro chỉ thêm 1 câu dẫn; code chèn opening và disclaimer. "
                "Không có chỉ dẫn sân khấu trong vo. Không viết heading/chapter vào vo.",
                {**context, "outline": draft, "batch": draft[offset:offset+3]})
            batch = response.get("scenes", [])
            if not isinstance(batch, list) or [s.get("id") for s in batch if isinstance(s, dict)] != [s["id"] for s in draft[offset:offset+3]]:
                raise ValueError("AI trả thiếu hoặc đổi ID cảnh.")
            written.extend(batch)
        # Fixed strings are controlled locally, preserving the original identity.
        for sc in written:
            if sc.get("type") == "intro":
                sc["vo"] = self.profile["opening"] + self.profile["disclaimer"] + sc.get("vo", "").replace(self.profile["opening"], "").replace(self.profile["disclaimer"], "")
        if sum(sc.get("type") == "item" for sc in written) != len(topic["items"]):
            self.state["script_candidate"] = written
            raise ValueError("Số item trong kịch bản khác số mục của chủ đề. Chỉnh lại kịch bản trước khi tiếp tục.")
        for attempt in range(3):
            errors = scene_issues(written, self.profile)
            if not errors:
                break
            if attempt == 2:
                self.state["script_candidate"] = written
                raise ValueError("Kịch bản chưa đạt sau 2 vòng sửa:\n" + "\n".join(errors))
            self.progress(f"Kịch bản · sửa văn phong, vòng {attempt+1}/2")
            for offset in range(0, len(written), 3):
                batch = written[offset:offset+3]
                repaired = self.ask(
                    "EDIT: sửa lỗi lint nhưng KHÔNG đổi ID, ý nghĩa, số liệu, hedge, thứ tự hoặc loại cảnh. "
                    "Giữ nguyên opening và disclaimer nếu có. Xuất {scenes:[các object đầy đủ như đầu vào]}.",
                    {"scenes": batch, "lint_issues": errors, "sources": self.state["sources"]}).get("scenes", [])
                if not isinstance(repaired, list) or [s.get("id") for s in repaired if isinstance(s, dict)] != [s["id"] for s in batch]:
                    raise ValueError("Bản sửa đổi ID hoặc thiếu cảnh.")
                written[offset:offset+len(batch)] = repaired
        self.state["scenes"] = written
        self.state.pop("script_candidate", None)
        self.state["thumb_text"] = topic["thumb_text"]
        self.progress("Kịch bản · đánh giá văn nói")
        judgement = self.ask(
            "JUDGE: chấm văn nói tiếng Nhật 5 tiêu chí, mỗi tiêu chí 1–5: nhịp nói, từ vựng, liên từ, "
            "đa dạng đuôi câu, ít văn dịch máy. Xuất {scores:[5 số],worst_sentence,fix}. "
            "Không chấm thấp vì opening/disclaimer cố định.", {"scenes": written})
        scores = judgement.get("scores", [])
        if not isinstance(scores, list) or len(scores) != 5 or not all(type(n) in (int, float) and 1 <= n <= 5 for n in scores):
            raise ValueError("Bản đánh giá văn phong không đúng định dạng.")
        judgement["average"] = sum(scores)/5
        self.state["voice_judgement"] = judgement
        if judgement["average"] < 4:
            self.state["script_candidate"] = written
            raise ValueError("Văn phong dưới 4/5; xem nhận xét, biên tập rồi lưu lại kịch bản.")

    def validate_script(self):
        self.episode.require("script")
        errors = scene_issues(self.state["scenes"], self.profile)
        if errors:
            raise ValueError("\n".join(errors))

    def stage_voice(self):
        self.validate_script()
        from channel.media import synthesize_episode, subtitle_files
        media = synthesize_episode(self.state["scenes"], self.episode.folder / "audio", self.profile,
                                   self.state["assets"], self.progress, self.stop.is_set)
        ass, srt = subtitle_files(self.episode.folder / "subtitles", media["cues"], self.profile)
        self.state["media"] = {**media, "ass_path": ass, "srt_path": srt}

    def stage_images(self):
        self.validate_script()
        from channel.integrations import resolve_flow_project
        assets = self.state["assets"]
        base = assets.get("flow_url", "http://127.0.0.1:8100").rstrip("/")
        flow_info = resolve_flow_project(base, assets.get("flow_project_id", ""))
        project = flow_info["project_id"]
        self.state["flow_project"] = flow_info
        self.progress(f"FlowKit · {flow_info.get('project_name') or project} · {flow_info['source']}")
        client = requests.Session()
        if not flow_info["extension_connected"]:
            raise ValueError("Chrome Extension chưa kết nối Google Flow.")
        folder = self.episode.folder / "images"; folder.mkdir(exist_ok=True)
        for sc in self.state["scenes"]:
            self.check_stop()
            prompt = image_prompt(sc["visual_prompt"], self.profile)
            digest = hashlib.sha256(prompt.encode()).hexdigest()
            path = folder / f"{sc['id']}_{digest[:12]}.png"
            if not path.exists():
                self.progress(f"Ảnh nền · {sc['id']}")
                response = client.post(base + "/api/flow/generate-image", json={
                    "prompt": prompt, "project_id": project, "aspect_ratio": "IMAGE_ASPECT_RATIO_LANDSCAPE", "count": 1,
                }, timeout=300)
                response.raise_for_status()
                media = response.json().get("media", [])
                url = next((m.get("image", {}).get("generatedImage", {}).get("fifeUrl") for m in media if m.get("image", {}).get("generatedImage", {}).get("fifeUrl")), None)
                if not url:
                    raise ValueError("Flow không trả ảnh. Kiểm tra extension và tài khoản.")
                download = client.get(url, timeout=90); download.raise_for_status()
                temporary = path.with_suffix(".pending.png"); temporary.write_bytes(download.content)
                with Image.open(temporary) as image:
                    image.verify()
                temporary.replace(path)
            sc.update(image_path=str(path), image_prompt=prompt)
            self.episode.save()
        # On rerun, successful backgrounds with identical prompts are reused.

    def stage_thumbnails(self):
        self.validate_script()
        from channel.artwork import thumbnails
        count = sum(s["type"] == "item" for s in self.state["scenes"])
        pinned = self.episode.freeze_brand_assets()
        self.state["thumbnails"] = thumbnails(self.episode.folder / "thumbnails", self.state["thumb_text"], count,
                                               self.profile, pinned)

    def stage_seo(self):
        self.episode.require("voice")
        topic, media = self.topic(), self.state["media"]
        context = {"topic": topic, "script": self.state["scenes"], "sources": self.state["sources"], "chapters": media["chapters"]}
        task = ("SEO: xuất {titles:[3],description,tags:[15],pinned_comment,playlist}. "
                "Mỗi title có keyword nguyên văn, số, 【】, ≤48 ký tự. 3 câu đầu description chứa keyword. "
                "Không thêm chapters, disclaimer, credit vào description vì code sẽ nối từ dữ liệu thật. "
                "Không bịa ngày, nguồn, số liệu hoặc hứa lợi nhuận.")
        seo = self.ask(task, context)
        for attempt in range(2):
            errors = seo_issues(seo, self.profile, topic["keyword"])
            if not errors:
                break
            if attempt:
                raise ValueError("SEO chưa đạt:\n" + "\n".join(errors))
            seo = self.ask(task + " Sửa các lỗi trong lint_issues.", {**context, "previous": seo, "lint_issues": errors})
        seo["chapters"] = media["chapters"]
        seo["description"] = re.sub(r"(?m)^\s*\d{1,2}:\d{2}(?::\d{2})?[^\n]*", "", seo["description"])
        seo["description"] = seo["description"].replace(self.profile["disclaimer"], "").strip()
        seo["description"] += "\n\n" + "\n".join(media["chapters"]) + "\n\n" + self.profile["disclaimer"] + "\n" + media["voice_credit"]
        if self.state["sources"].strip():
            seo["description"] += "\n\n出典・参考資料\n" + self.state["sources"].strip()
        if "補助金" in json.dumps(topic, ensure_ascii=False) or "助成金" in json.dumps(topic, ensure_ascii=False):
            reference_date = date.today()
            seo["description"] += f"\n{reference_date.year}年{reference_date.month}月時点。最新は公式サイトで確認を。"
        self.state["seo"] = seo
        write_json_atomic(self.episode.folder / "seo.json", seo)
        (self.episode.folder / "youtube_description.txt").write_text(seo["description"], encoding="utf-8")

    def stage_render(self):
        self.episode.require("voice", "images", "thumbnails", "seo")
        self.validate_script()
        if not self.state.get("research_reviewed"):
            raise ValueError("Duyệt nguồn và nội dung trong tab Kiểm tra trước khi xuất video tài chính.")
        from channel.artwork import scene_frame, mascot_asset, font_at
        from video.render_engine import RenderEngine
        assets = self.episode.freeze_brand_assets()
        font_at(assets.get("font"), 48)
        for pose in self.profile["poses"]:
            mascot_asset(assets.get("mascot_dir", ""), pose)
        scene_map = {s["id"]: s for s in self.state["scenes"]}
        output = self.episode.folder / "frames"; output.mkdir(exist_ok=True)
        segments = []
        frame_boundary = 0
        for index, entry in enumerate(self.state["media"]["schedule"]):
            self.check_stop()
            scene = scene_map[entry["id"]]
            frame = scene_frame(scene, output / f"{index:03}.png", self.profile, assets, entry["bumper"])
            end_frame = round((entry["start"] + entry["duration"])*30)
            segments.append({"id": scene["id"], "image_path": frame, "duration": (end_frame-frame_boundary)/30, "effect": ""})
            frame_boundary = end_frame
        self.progress("Đang xuất video 1080p · phụ đề Nhật, mascot, telop và âm thanh")
        engine = RenderEngine(str(self.episode.folder))
        path = engine.render(segments, self.state["media"]["audio_path"], self.state["media"]["ass_path"],
                             bgm_path=assets.get("bgm") or None, font_path=assets.get("font"),
                             cancelled=self.stop.is_set)
        self.state["video_path"] = path
