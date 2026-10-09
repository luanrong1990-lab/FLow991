"""Manage the project-local VOICEVOX Engine process.

The packaged engine is intentionally kept out of the Python environment.  The
application talks to it through VOICEVOX's public HTTP API, so upgrades can be
performed by replacing the runtime directory without changing app packages.
"""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = PROJECT_ROOT / ".runtime" / "voicevox_engine"
LOG_PATH = PROJECT_ROOT / "logs" / "voicevox_engine.log"
DEFAULT_URL = "http://127.0.0.1:50021"


class VoicevoxRuntime:
    """Start and stop only the engine process owned by this application."""

    def __init__(self):
        self.process: subprocess.Popen | None = None
        self._log_handle = None
        self._lock = threading.RLock()

    @staticmethod
    def health(url=DEFAULT_URL, timeout=2):
        try:
            with urllib.request.urlopen(url.rstrip("/") + "/version", timeout=timeout) as response:
                version = json.loads(response.read().decode("utf-8"))
                return {"running": response.status == 200, "version": str(version)}
        except Exception:
            return {"running": False, "version": ""}

    @staticmethod
    def executable():
        configured = os.getenv("VOICEVOX_ENGINE_EXE", "").strip()
        if configured and Path(configured).is_file():
            return Path(configured)
        direct = RUNTIME_ROOT / "run.exe"
        if direct.is_file():
            return direct
        matches = sorted(RUNTIME_ROOT.glob("**/run.exe"), key=lambda p: len(p.parts))
        return matches[0] if matches else None

    def status(self, url=DEFAULT_URL):
        health = self.health(url)
        executable = self.executable()
        return {
            **health,
            "installed": executable is not None,
            "executable": str(executable) if executable else "",
            "owned_by_app": bool(self.process and self.process.poll() is None),
            "pid": self.process.pid if self.process and self.process.poll() is None else None,
        }

    def start(self, url=DEFAULT_URL, timeout=90):
        with self._lock:
            status = self.status(url)
            if status["running"]:
                status["message"] = "VOICEVOX Engine đã chạy sẵn."
                return status

            executable = self.executable()
            if executable is None:
                raise FileNotFoundError(
                    "Chưa tìm thấy VOICEVOX Engine trong D:\\Flow\\.runtime\\voicevox_engine."
                )

            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._log_handle = open(LOG_PATH, "a", encoding="utf-8")
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            self.process = subprocess.Popen(
                [str(executable), "--host", "127.0.0.1", "--port", "50021"],
                cwd=str(executable.parent),
                stdin=subprocess.DEVNULL,
                stdout=self._log_handle,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                return_code = self.process.returncode
                self.stop()
                raise RuntimeError(
                    f"VOICEVOX Engine đã thoát với mã {return_code}. "
                    f"Xem log: {LOG_PATH}"
                )
            health = self.health(url)
            if health["running"]:
                status = self.status(url)
                status["message"] = "Ứng dụng đã tự khởi động VOICEVOX Engine."
                return status
            time.sleep(0.5)
        self.stop()
        raise TimeoutError(f"VOICEVOX Engine không sẵn sàng sau {timeout} giây. Xem log: {LOG_PATH}")

    def stop(self):
        with self._lock:
            process, self.process = self.process, None
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            if self._log_handle:
                self._log_handle.close()
                self._log_handle = None


voicevox_runtime = VoicevoxRuntime()
atexit.register(voicevox_runtime.stop)


def start_voicevox_engine(url=DEFAULT_URL):
    return voicevox_runtime.start(url)


def voicevox_engine_status(url=DEFAULT_URL):
    return voicevox_runtime.status(url)


def stop_voicevox_engine():
    voicevox_runtime.stop()
    return voicevox_runtime.status()
