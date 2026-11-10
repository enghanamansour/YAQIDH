"""Starts the app under test for the QA checks and stops it afterwards. Plain code, no agent involved."""

import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import AbstractContextManager
from pathlib import Path

from src.tools.base import ToolError


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class AppServer(AbstractContextManager):
    """Runs `python -m <module>` with PORT and a throwaway database, and waits until it answers."""

    def __init__(self, module: str = "demo_app.app", cwd: Path | None = None, startup_timeout: float = 30):
        self.module = module
        self.cwd = Path(cwd) if cwd else Path.cwd()
        self.startup_timeout = startup_timeout
        self._proc: subprocess.Popen | None = None
        self._tmp: tempfile.TemporaryDirectory | None = None
        self._log: tempfile._TemporaryFileWrapper | None = None

    def __enter__(self) -> str:
        port = _free_port()
        self._tmp = tempfile.TemporaryDirectory()
        self._log = tempfile.TemporaryFile("w+")
        env = {**os.environ, "PORT": str(port), "MAKTABTI_DB": str(Path(self._tmp.name) / "test.db")}
        self._proc = subprocess.Popen(
            [sys.executable, "-m", self.module],
            cwd=self.cwd, env=env, stdout=self._log, stderr=subprocess.STDOUT,
            start_new_session=True,  # own process group, so the debug reloader's child is stopped too
        )
        url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                break
            try:
                urllib.request.urlopen(url, timeout=2).close()
                return url
            except urllib.error.HTTPError:
                return url
            except (urllib.error.URLError, OSError):
                time.sleep(0.3)
        self._log.seek(0)
        tail = self._log.read()[-400:]
        self.__exit__()
        raise ToolError(f"the app under test did not start ({self.module}): {tail}")

    @staticmethod
    def _stop(proc: subprocess.Popen) -> None:
        """Stops the app and its children (the debug reloader starts one). Windows has no process groups."""
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            return
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def __exit__(self, *exc):
        if self._proc and self._proc.poll() is None:
            self._stop(self._proc)
        if self._log is not None:
            self._log.close()
        if self._tmp is not None:
            self._tmp.cleanup()
        self._proc = self._tmp = self._log = None
        return False
