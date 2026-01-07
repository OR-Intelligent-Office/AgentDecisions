from __future__ import annotations

import os
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence


@dataclass
class ManagedProcess:
    name: str
    cmd: Sequence[str]
    cwd: Path
    env: dict[str, str]
    show_logs: bool = False
    _p: Optional[subprocess.Popen] = None

    def start(self) -> None:
        if self._p and self._p.poll() is None:
            return

        stdout = None if self.show_logs else subprocess.DEVNULL
        stderr = None if self.show_logs else subprocess.DEVNULL

        self._p = subprocess.Popen(
            list(self.cmd),
            cwd=str(self.cwd),
            env=self.env,
            stdout=stdout,
            stderr=stderr,
        )

    def is_running(self) -> bool:
        return self._p is not None and self._p.poll() is None

    def stop(self, timeout_seconds: float = 5.0) -> None:
        if not self._p:
            return
        if self._p.poll() is not None:
            return

        try:
            # macOS/Linux friendly
            self._p.terminate()
            self._p.wait(timeout=timeout_seconds)
            return
        except Exception:
            pass

        try:
            self._p.kill()
        except Exception:
            pass


class ProcessManager:
    def __init__(self, show_logs: bool = False):
        self.show_logs = show_logs
        self._procs: list[ManagedProcess] = []

    def add(self, p: ManagedProcess) -> None:
        self._procs.append(p)

    def start_all(self) -> None:
        for p in self._procs:
            p.start()

    def stop_all(self) -> None:
        for p in reversed(self._procs):
            p.stop()


def project_root() -> Path:
    # AgentDecisions/orchestrator/process_manager.py -> AgentDecisions -> project root
    return Path(__file__).resolve().parents[2]


def default_env() -> dict[str, str]:
    env = dict(os.environ)
    # Ensure python uses current venv interpreter libs; keep PATH unchanged.
    return env


def python_cmd() -> str:
    return sys.executable


def kill_process_on_port(port: int) -> None:
    """Kill process using the given port (macOS/Linux)."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if result.returncode == 0 and result.stdout.strip():
            pid = result.stdout.strip()
            subprocess.run(["kill", pid], timeout=2.0)
    except Exception:
        pass  # Ignore errors (port might be free, lsof might not exist, etc.)


