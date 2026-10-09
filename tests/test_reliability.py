import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from utils.json_store import write_json_atomic
from config import session_manager, config_manager
from video.render_engine import RenderEngine


class ReliabilityTests(unittest.TestCase):
    def test_failed_json_save_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            write_json_atomic(path, {"text": "Tiếng Việt"})
            with self.assertRaises(TypeError):
                write_json_atomic(path, {"invalid": object()})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"text": "Tiếng Việt"})
            self.assertEqual(list(Path(folder).iterdir()), [path])

    def test_failed_replace_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            write_json_atomic(path, {"old": True})
            with patch("utils.json_store.os.replace", side_effect=PermissionError):
                with self.assertRaises(PermissionError):
                    write_json_atomic(path, {"new": True})
            self.assertEqual(json.loads(path.read_text()), {"old": True})
            self.assertEqual(list(Path(folder).iterdir()), [path])

    def test_non_object_settings_and_session(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            path.write_text("[]")
            with patch.object(session_manager, "SESSION_FILE", path):
                self.assertEqual(session_manager.load_session(), {})
            with patch.object(config_manager, "SETTINGS_FILE", path):
                self.assertEqual(config_manager.load_settings(), {})

    def test_clip_failure_stops_before_concat(self):
        with tempfile.TemporaryDirectory() as folder:
            asset = Path(folder) / "input"
            asset.touch()
            engine = RenderEngine(folder)
            failure = subprocess.CompletedProcess([], 1, stderr=b"broken input")
            with patch("video.render_engine.subprocess.run", return_value=failure) as run:
                with self.assertRaisesRegex(RuntimeError, "broken input"):
                    engine.render([{"image_path": str(asset), "duration": 1}], str(asset), None)
                self.assertEqual(run.call_count, 1)

    def test_invalid_duration_rejected_before_ffmpeg(self):
        with tempfile.TemporaryDirectory() as folder:
            asset = Path(folder) / "input"
            asset.touch()
            engine = RenderEngine(folder)
            for duration in (0, -1, float("nan"), float("inf")):
                with self.subTest(duration=duration), patch("video.render_engine.subprocess.run") as run:
                    with self.assertRaises(ValueError):
                        engine.render([{"duration": duration}], str(asset), None)
                    run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
