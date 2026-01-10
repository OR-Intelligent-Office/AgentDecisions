from __future__ import annotations

import os
import signal
import subprocess
import sys
import logging
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

logger = logging.getLogger(__name__)

def _logs_dir() -> Path:
    # AgentDecisions/orchestrator/process_manager.py -> AgentDecisions
    base = Path(__file__).resolve().parents[1]
    return base / ".agent_logs"


@dataclass
class ManagedProcess:
    name: str
    cmd: Sequence[str]
    cwd: Path
    env: dict[str, str]
    show_logs: bool = False
    _p: Optional[subprocess.Popen] = None
    _log_path: Optional[Path] = None
    _log_fh: Optional[object] = None

    def start(self) -> None:
        if self._p and self._p.poll() is None:
            return

        stdout = None
        stderr = None
        if self.show_logs:
            stdout = None
            stderr = None
        else:
            # Write agent output to a file so failures are debuggable without spamming console.
            try:
                d = _logs_dir()
                d.mkdir(parents=True, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                self._log_path = d / f"{self.name}-{ts}.log"
                self._log_fh = open(self._log_path, "w", encoding="utf-8")
                stdout = self._log_fh
                stderr = self._log_fh
            except Exception as e:
                logger.warning("Failed to open log file for '%s': %s (falling back to DEVNULL)", self.name, e)
                stdout = subprocess.DEVNULL
                stderr = subprocess.DEVNULL

        try:
            self._p = subprocess.Popen(
                list(self.cmd),
                cwd=str(self.cwd),
                env=self.env,
                stdout=stdout,
                stderr=stderr,
                # Put the process in its own session/process group (macOS/Linux),
                # so we can terminate the whole tree reliably.
                start_new_session=True,
            )
        except Exception as e:
            logger.warning(
                "Failed to start process '%s' (cwd=%s, cmd=%s): %s",
                self.name,
                str(self.cwd),
                list(self.cmd),
                e,
            )
            self._p = None
            self._close_log()

    def is_running(self) -> bool:
        return self._p is not None and self._p.poll() is None

    def exit_code(self) -> Optional[int]:
        if not self._p:
            return None
        return self._p.poll()

    def log_path(self) -> Optional[Path]:
        return self._log_path

    def stop(self, timeout_seconds: float = 5.0) -> None:
        if not self._p:
            self._close_log()
            return
        if self._p.poll() is not None:
            self._close_log()
            return

        # Best-effort: terminate whole process group (agent + any children).
        try:
            os.killpg(self._p.pid, signal.SIGTERM)
            self._p.wait(timeout=timeout_seconds)
            self._close_log()
            return
        except Exception:
            pass

        try:
            os.killpg(self._p.pid, signal.SIGKILL)
            self._p.wait(timeout=timeout_seconds)
            self._close_log()
            return
        except Exception:
            pass

        # Fallback: kill just the parent process.
        try:
            self._p.terminate()
            self._p.wait(timeout=timeout_seconds)
            self._close_log()
            return
        except Exception:
            pass

        try:
            self._p.kill()
        except Exception:
            pass
        finally:
            self._close_log()

    def _close_log(self) -> None:
        try:
            if self._log_fh:
                self._log_fh.close()
        except Exception:
            pass
        self._log_fh = None


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
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2.0,
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = [p.strip() for p in result.stdout.splitlines() if p.strip()]
            for pid in pids:
                # Silence kill output; ignore failures (process may have exited already).
                subprocess.run(
                    ["kill", pid],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2.0,
                )
    except Exception:
        pass  # Ignore errors (port might be free, lsof might not exist, etc.)


