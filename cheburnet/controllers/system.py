from __future__ import annotations

import ctypes
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


IS_WINDOWS = os.name == "nt"
CREATE_NO_WINDOW = 0x08000000 if IS_WINDOWS else 0
SW_HIDE = 0
SW_SHOWNORMAL = 1


@dataclass
class CommandResult:
    ok: bool
    command: list[str]
    code: int
    stdout: str = ""
    stderr: str = ""

    @property
    def text(self) -> str:
        return "\n".join(part for part in (self.stdout.strip(), self.stderr.strip()) if part)


def is_admin() -> bool:
    if not IS_WINDOWS:
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def enable_dpi_awareness() -> None:
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def run_elevated(
    executable: str,
    args: list[str] | str,
    cwd: str | Path | None = None,
    show: bool = True,
) -> None:
    if not IS_WINDOWS:
        raise RuntimeError("Elevated ShellExecute is only available on Windows.")
    parameters = args if isinstance(args, str) else subprocess.list2cmdline(args)
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        executable,
        parameters,
        str(cwd) if cwd else None,
        SW_SHOWNORMAL if show else SW_HIDE,
    )
    if result <= 32:
        raise RuntimeError(f"UAC launch failed with ShellExecute code {result}.")


def split_command_line(command_line: str) -> list[str]:
    if not IS_WINDOWS:
        return shlex.split(command_line)
    argc = ctypes.c_int()
    command_line_to_argv = ctypes.windll.shell32.CommandLineToArgvW
    command_line_to_argv.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    command_line_to_argv.restype = ctypes.POINTER(ctypes.c_wchar_p)
    argv = command_line_to_argv(command_line, ctypes.byref(argc))
    if not argv:
        raise RuntimeError("CommandLineToArgvW failed.")
    try:
        return [argv[index] for index in range(argc.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(argv)


def find_executable(name: str, candidates: list[str] | None = None) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for candidate in candidates or []:
        path = Path(candidate)
        if path.exists():
            return str(path)
    return None


def run_command(
    command: list[str],
    cwd: str | Path | None = None,
    timeout: int | None = None,
    no_window: bool = True,
) -> CommandResult:
    flags = CREATE_NO_WINDOW if no_window else 0
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=flags,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        return CommandResult(False, command, 127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return CommandResult(False, command, 124, stdout, stderr or "Command timed out")
    return CommandResult(
        completed.returncode == 0,
        command,
        completed.returncode,
        completed.stdout,
        completed.stderr,
    )


def open_folder(path: str | Path) -> None:
    if IS_WINDOWS:
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    subprocess.Popen(["xdg-open", str(path)])
