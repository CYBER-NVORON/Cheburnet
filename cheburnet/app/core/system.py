from __future__ import annotations

import ctypes
import os
import platform
import subprocess
import sys
from pathlib import Path

IS_WINDOWS = os.name == "nt"
CREATE_NO_WINDOW = 0x08000000 if IS_WINDOWS else 0
SW_HIDE = 0
SW_SHOWNORMAL = 1


def is_admin() -> bool:
    if IS_WINDOWS:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return os.geteuid() == 0 if hasattr(os, "geteuid") else False


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


def relaunch_as_admin(args: list[str] | None = None) -> None:
    if not IS_WINDOWS:
        raise RuntimeError("Автоперезапуск с правами администратора доступен только в Windows.")
    if args is None:
        launch_args = sys.argv[1:] if getattr(sys, "frozen", False) else sys.argv
    else:
        launch_args = args
    parameters = subprocess.list2cmdline(launch_args)
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        parameters,
        str(Path.cwd()),
        SW_SHOWNORMAL,
    )
    if result <= 32:
        raise RuntimeError(f"Пользователь отменил UAC или ShellExecute вернул код {result}.")


def open_path(path: str | Path) -> None:
    target = str(path)
    if IS_WINDOWS:
        os.startfile(target)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", target])
    else:
        subprocess.Popen(["xdg-open", target])


def platform_key() -> tuple[str, str]:
    raw_system = platform.system().lower()
    if raw_system.startswith("windows") or IS_WINDOWS:
        system = "windows"
    elif raw_system.startswith("darwin"):
        system = "darwin"
    elif raw_system.startswith("linux"):
        system = "linux"
    else:
        raise RuntimeError(f"ОС не поддерживается: {platform.system()}")

    machine = platform.machine().lower()
    arch_map = {
        "amd64": "amd64",
        "x86_64": "amd64",
        "x64": "amd64",
        "arm64": "arm64",
        "aarch64": "arm64",
        "i386": "386",
        "i686": "386",
        "x86": "386",
    }
    arch = arch_map.get(machine)
    if not arch:
        raise RuntimeError(f"Архитектура не поддерживается: {platform.machine()}")
    return system, arch
