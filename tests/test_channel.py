import copy
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import wave

from channel.rules import profile_snapshot, narration_issues, scene_issues, seo_issues, image_prompt, thumb_issues
from channel.pipeline import Episode, ChannelPipeline
from channel.media import synthesize_episode, timestamp, subtitle_files, chapters
from channel.integrations import discover_flowkit, resolve_flow_project, voicevox_info, synthesize_voicevox_preview
from channel.voicevox_runtime import VoicevoxRuntime


class FakeResponse:
    def __init__(self, data=None, content=b""):
        self.data, self.content = data, content
    def raise_for_status(self): pass
    def json(self): return self.data


def valid_scenes(profile):
    scenes = []
    number = 0
    for index, kind in enumerate(["hook", "intro", "item", "mid", "item", "recap", "outro"], 1):
        if kind == "item": number += 1
        vo = "家計を見直します。小さな一歩です。"
        if kind == "hook": vo = "家計が気になりますか？今日は2つを見ます。"
        if kind == "intro": vo = profile["opening"] + profile["disclaimer"] + vo
        scenes.append({"id": f"SC{index:02}", "type": kind, "number": number if kind == "item" else 0,
                       "vo": vo, "telop": "家計の見直し", "emotion": "think", "visual_prompt": "a household ledger on a desk"})
    return scenes


class ChannelRulesTests(unittest.TestCase):
    def setUp(self): self.profile = profile_snapshot()

    def test_original_bible_extracted(self):
        self.assertIn("静かに稼ぐ研究室", self.profile["bible"])
        self.assertIn("Telop ≤13", self.profile["bible"])

    def test_fixed_disclaimer_is_exempt_but_claim_is_not(self):
        self.assertEqual(narration_issues(self.profile["opening"] + self.profile["disclaimer"], self.profile), [])
        self.assertTrue(narration_issues("利益の保証です。", self.profile))

    def test_precise_endings_and_tts_symbols(self):
        self.assertFalse(narration_issues("安いです。助かるんです。変わるんですね。", self.profile))
        self.assertTrue(narration_issues("安いです。高いです。広いです。", self.profile))
        for text in ("PCです。", "20％です。", "[注意]です。", "絶対です！"):
            self.assertTrue(narration_issues(text, self.profile), text)

    def test_scene_structure_and_identity(self):
        scenes = valid_scenes(self.profile)
        self.assertEqual(scene_issues(scenes, self.profile), [])
        scenes[1]["vo"] = "挨拶です。"
        self.assertTrue(scene_issues(scenes, self.profile))
        scenes = valid_scenes(self.profile)
        scenes[2]["id"] = "../unsafe"
        self.assertTrue(scene_issues(scenes, self.profile))

    def test_style_lock_is_idempotent(self):
        prompt = image_prompt("A ledger", self.profile)
        self.assertEqual(image_prompt(prompt, self.profile), prompt)
        self.assertTrue(prompt.startswith(self.profile["style_lock"]))
        self.assertTrue(prompt.endswith(self.profile["negative"]))

    def test_thumbnail_and_title_gate(self):
        self.assertFalse(thumb_issues(["家計の見直し", "2つの習慣"], self.profile))
        self.assertTrue(thumb_issues(["あ"*15], self.profile))
        seo = {"titles": ["【家計】2つの習慣"]*3, "tags": [f"タグ{i}" for i in range(15)],
               "description": "家計を見直します。", "pinned_comment": "何から始めますか？"}
        self.assertEqual(seo_issues(seo, self.profile, "家計"), [])
        seo["titles"][0] = "【家計】絶対に増える2つの習慣"
        self.assertTrue(seo_issues(seo, self.profile, "家計"))

    def test_timestamp_carry(self):
        self.assertEqual(timestamp(59.999), "0:01:00.00")
        self.assertEqual(timestamp(3599.9996, True), "01:00:00,000")


class EpisodeTests(unittest.TestCase):
    def test_brand_snapshot_survives_source_edit(self):
        with tempfile.TemporaryDirectory() as folder:
            font = Path(folder)/"font.ttf"; font.write_bytes(b"original")
            ep = Episode.create(folder, "ep001", "P1", "", "", {"font": str(font)})
            pinned = ep.freeze_brand_assets()
            font.write_bytes(b"new version")
            self.assertEqual(Path(ep.freeze_brand_assets()["font"]).read_bytes(), b"original")

    def test_mock_ai_script_pipeline_injects_bible_and_fixed_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            ep = Episode.create(folder, "ep001", "P1", "brief", "source", {})
            scenes = valid_scenes(ep.profile)
            # This fixture uses a manually selected two-item topic to keep the test small.
            topic = {"title_seed": "家計2選", "items": [{}, {}], "thumb_text": ["家計2選"], "keyword": "家計"}
            ep.state.update(topics=[topic], selected_topic=0)
            ep.state["stages"]["topics"] = "done"
            ai = Mock()
            prompts = []
            def generate(system, message):
                prompts.append(system)
                context = json.loads(message)
                if "DRAFT: 出力" in system: raise AssertionError("wrong language")
                if "\nDRAFT:" in system: return json.dumps({"scenes": scenes}, ensure_ascii=False)
                if "\nWRITE:" in system: return json.dumps({"scenes": context["batch"]}, ensure_ascii=False)
                if "\nJUDGE:" in system: return json.dumps({"scores": [4,4,4,4,4], "fix": ""})
                raise AssertionError(system[-100:])
            ai.generate.side_effect = generate
            ChannelPipeline(ep, ai=ai).run("script")
            self.assertEqual(ep.state["stages"]["script"], "done")
            self.assertEqual(ep.state["scenes"][1]["vo"].count(ep.profile["opening"]), 1)
            self.assertEqual(len(prompts), 5)
            self.assertTrue(all(ep.profile["bible"] in prompt for prompt in prompts))

    def test_seo_uses_real_chapters_and_voice_credit(self):
        with tempfile.TemporaryDirectory() as folder:
            ep = Episode.create(folder, "ep001", "P1", "brief", "", {})
            ep.state.update(topics=[{"keyword": "家計"}], selected_topic=0,
                            media={"chapters": ["00:00 オープニング", "02:17 見直し"], "voice_credit": "音声：VOICEVOX：テスト"})
            ep.state["stages"].update(topics="done", voice="done")
            ai = Mock(); ai.generate.return_value = json.dumps({"titles": ["【家計】2つの習慣"]*3,
                "description": "家計を見直します。", "tags": [f"タグ{i}" for i in range(15)], "pinned_comment": "何を見ますか？"}, ensure_ascii=False)
            ChannelPipeline(ep, ai=ai).run("seo")
            description = ep.state["seo"]["description"]
            self.assertIn("02:17 見直し", description)
            self.assertIn("音声：VOICEVOX：テスト", description)
            self.assertIn(ep.profile["disclaimer"], description)

    def test_snapshot_and_downstream_invalidation(self):
        with tempfile.TemporaryDirectory() as folder:
            ep = Episode.create(folder, "ep001", "P1", "brief", "sources", {})
            ep.state["stages"] = {key: "done" for key in ["topics", "script", "voice", "images", "thumbnails", "seo", "render"]}
            ep.state["research_reviewed"] = True
            ep.save_script(valid_scenes(ep.profile))
            self.assertEqual(ep.state["stages"], {"topics": "done", "script": "done"})
            self.assertFalse(ep.state["research_reviewed"])
            self.assertEqual(Episode(ep.folder).profile, ep.profile)
            with self.assertRaises(FileExistsError): Episode.create(folder, "ep001", "P1", "", "", {})
            with self.assertRaises(ValueError): Episode.create(folder, "../outside", "P1", "", "", {})

    def test_api_failure_persists_failed_state(self):
        with tempfile.TemporaryDirectory() as folder:
            ep = Episode.create(folder, "ep001", "P1", "brief", "", {})
            ai = Mock(); ai.generate.side_effect = RuntimeError("offline")
            with self.assertRaisesRegex(RuntimeError, "offline"):
                ChannelPipeline(ep, ai=ai).run("topics")
            self.assertEqual(Episode(ep.folder).state["stages"]["topics"], "failed")

    def test_invalid_script_does_not_overwrite_saved_script(self):
        with tempfile.TemporaryDirectory() as folder:
            ep = Episode.create(folder, "ep001", "P1", "brief", "", {})
            scenes = valid_scenes(ep.profile); ep.save_script(scenes)
            broken = copy.deepcopy(scenes); broken[0]["vo"] = "絶対です。"
            with self.assertRaises(ValueError): ep.save_script(broken)
            self.assertEqual(Episode(ep.folder).state["scenes"], scenes)

    def test_render_requires_review_before_ffmpeg(self):
        with tempfile.TemporaryDirectory() as folder:
            ep = Episode.create(folder, "ep001", "P1", "brief", "", {})
            ep.save_script(valid_scenes(ep.profile))
            ep.state["stages"].update({s: "done" for s in ("voice", "images", "thumbnails", "seo")})
            with self.assertRaisesRegex(ValueError, "Duyệt nguồn"):
                ChannelPipeline(ep).run("render")


class MediaTests(unittest.TestCase):
    def test_voice_timings_bumpers_cache_and_subtitles(self):
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as writer:
            writer.setnchannels(1); writer.setsampwidth(2); writer.setframerate(24000)
            writer.writeframes(b"\0\0"*2400)
        client = Mock()
        speakers = Mock(); speakers.json.return_value = [{"name": "ずんだもん", "styles": [{"id": 3, "name": "ノーマル"}]}]
        client.get.return_value = speakers
        query = Mock(); query.json.return_value = {}
        audio = Mock(); audio.content = buffer.getvalue()
        client.post.side_effect = lambda url, **kw: query if url.endswith("audio_query") else audio
        profile = profile_snapshot()
        scenes = [{"id": "SC01", "type": "hook", "telop": "開始", "vo": "家計です。"},
                  {"id": "SC02", "type": "item", "number": 1, "telop": "見直し", "vo": "家計です。"}]
        with tempfile.TemporaryDirectory() as folder, patch("channel.media.requests.Session", return_value=client):
            media = synthesize_episode(scenes, folder, profile, {}, lambda s: None, lambda: False)
            self.assertAlmostEqual(media["duration"], 2.2)
            self.assertAlmostEqual(media["cues"][1]["start"], 2.1)
            self.assertEqual(client.post.call_count, 2)  # identical text reuses WAV cache
            self.assertIn("ずんだもん", media["voice_credit"])
            self.assertEqual(media["chapters"][0], "00:00 オープニング")
            ass, srt = subtitle_files(folder, media["cues"], profile)
            self.assertIn("00:00:02,100", Path(srt).read_text(encoding="utf-8"))
            self.assertIn("Noto Sans JP", Path(ass).read_text(encoding="utf-8"))


class IntegrationTests(unittest.TestCase):
    def test_voicevox_runtime_reuses_an_existing_engine(self):
        runtime = VoicevoxRuntime()
        with patch.object(runtime, "health", return_value={"running": True, "version": "0.25.2"}), \
             patch.object(runtime, "executable", return_value=Path("run.exe")):
            status = runtime.start()
        self.assertTrue(status["running"])
        self.assertFalse(status["owned_by_app"])
        self.assertIn("đã chạy sẵn", status["message"])

    def test_flowkit_uses_active_google_flow_uuid(self):
        project_id = "85222c0e-de50-4e6f-85dd-0d33d1eb127d"
        client = Mock()
        client.get.side_effect = [
            FakeResponse({"extension_connected": True}),
            FakeResponse({"project_id": project_id, "project_name": "Japan Channel", "source": "explicit"}),
            FakeResponse({"transport": "batch", "flow_project_id": None}),
        ]
        with patch("channel.integrations.requests.Session", return_value=client):
            info = discover_flowkit()
        self.assertEqual(info["project_id"], project_id)
        self.assertEqual(info["project_name"], "Japan Channel")
        self.assertTrue(info["extension_connected"])

    def test_flowkit_falls_back_to_pinned_project(self):
        project_id = "85222c0e-de50-4e6f-85dd-0d33d1eb127d"
        client = Mock()
        client.get.side_effect = [
            FakeResponse({"extension_connected": True}),
            FakeResponse({"project_id": None, "source": "none"}),
            FakeResponse({"transport": "batch", "flow_project_id": project_id}),
        ]
        with patch("channel.integrations.requests.Session", return_value=client):
            info = resolve_flow_project("http://127.0.0.1:8100", "")
        self.assertEqual(info["project_id"], project_id)
        self.assertEqual(info["source"], "pinned_flow_project")

    def test_voicevox_list_and_preview(self):
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as writer:
            writer.setnchannels(1); writer.setsampwidth(2); writer.setframerate(24000)
            writer.writeframes(b"\0\0" * 100)
        client = Mock()
        client.get.side_effect = [
            FakeResponse("0.25.2"),
            FakeResponse([{"name": "青山龍星", "styles": [{"id": 13, "name": "ノーマル"}]}]),
        ]
        with patch("channel.integrations.requests.Session", return_value=client):
            info = voicevox_info()
        self.assertEqual(info["speakers"][0]["id"], 13)
        self.assertIn("青山龍星", info["speakers"][0]["label"])

        client = Mock()
        client.post.side_effect = [FakeResponse({}), FakeResponse(content=buffer.getvalue())]
        with tempfile.TemporaryDirectory() as folder, patch("channel.integrations.requests.Session", return_value=client):
            output = synthesize_voicevox_preview("http://127.0.0.1:50021", 13, Path(folder) / "preview.wav")
            with wave.open(output, "rb") as reader:
                self.assertEqual(reader.getframerate(), 24000)


if __name__ == "__main__": unittest.main()
