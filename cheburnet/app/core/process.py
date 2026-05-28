from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from cheburnet.app.core.system import CREATE_NO_WINDOW, IS_WINDOWS

OutputCallback = Callable[[str], None]


def _hidden_startupinfo() -> subprocess.STARTUPINFO | None:
    if not IS_WINDOWS:
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return startupinfo


@dataclass(slots=True)
class CommandResult:
    ok: bool
    command: list[str]
    code: int
    stdout: str = ""
    stderr: str = ""

    @property
    def text(self) -> str:
        return "\n".join(part for part in (self.stdout.strip(), self.stderr.strip()) if part)


def run_command(command: list[str], cwd: str | Path | None = None, timeout: int | None = None) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW if IS_WINDOWS else 0,
            startupinfo=_hidden_startupinfo(),
        )
    except FileNotFoundError as exc:
        return CommandResult(False, command, 127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else "Команда превысила таймаут."
        return CommandResult(False, command, 124, stdout, stderr)
    return CommandResult(completed.returncode == 0, command, completed.returncode, completed.stdout, completed.stderr)


class ManagedProcess:
    def __init__(self, process: subprocess.Popen[str], reader: threading.Thread | None = None) -> None:
        self.process = process
        self.reader = reader

    @property
    def pid(self) -> int:
        return int(self.process.pid)

    def is_alive(self) -> bool:
        return self.process.poll() is None


class ProcessManager:
    def __init__(self, on_output: OutputCallback | None = None) -> None:
        self.on_output = on_output
        self.current: ManagedProcess | None = None

    def start_process(
        self,
        args: list[str],
        cwd: str | Path | None = None,
        on_output: OutputCallback | None = None,
    ) -> ManagedProcess:
        callback = on_output or self.on_output
        process = subprocess.Popen(
            args,
            cwd=str(cwd) if cwd else None,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW if IS_WINDOWS else 0,
            startupinfo=_hidden_startupinfo(),
        )
        reader = None
        if callback and process.stdout:
            reader = threading.Thread(target=self._read_output, args=(process, callback), daemon=True)
            reader.start()
        managed = ManagedProcess(process, reader)
        self.current = managed
        return managed

    def stop_current(self, timeout: float = 8.0) -> None:
        if not self.current:
            return
        current = self.current
        stopped = self.stop_process_tree(current.pid, timeout=timeout)
        if current.process.poll() is None and not stopped:
            raise RuntimeError(f"Процесс {current.pid} не остановился.")
        self.current = None

    def stop_process_tree(self, pid: int, timeout: float = 8.0) -> bool:
        if IS_WINDOWS:
            process = self.current.process if self.current and self.current.pid == pid else None
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=timeout)
                    return True
                except subprocess.TimeoutExpired:
                    pass
            result = run_command(["taskkill", "/PID", str(pid), "/T", "/F"], timeout=int(timeout) + 3)
            if process:
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
                return process.poll() is not None
            return result.ok

        if self.current and self.current.pid == pid and self.current.process.poll() is None:
            self.current.process.terminate()
            deadline = time.time() + timeout
            while time.time() < deadline:
                if self.current.process.poll() is not None:
                    return True
                time.sleep(0.1)
            self.current.process.kill()
            return True
        return True

    @staticmethod
    def is_process_alive(pid: int) -> bool:
        if IS_WINDOWS:
            result = run_command(["tasklist", "/FI", f"PID eq {pid}"], timeout=5)
            return result.ok and str(pid) in result.stdout
        result = run_command(["kill", "-0", str(pid)], timeout=5)
        return result.ok

    @staticmethod
    def _read_output(process: subprocess.Popen[str], callback: OutputCallback) -> None:
        assert process.stdout is not None
        for line in process.stdout:
            callback(line.rstrip())
