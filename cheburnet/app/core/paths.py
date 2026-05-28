from __future__ import annotations

import os
import sys
from pathlib import Path

from cheburnet.app.constants import APP_NAME


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def app_data_dir() -> Path:
    override = os.environ.get("CHEBURNET_HOME")
    if override:
        return _ensure_writable(Path(override))

    candidates: list[Path] = []
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(Path(appdata) / APP_NAME)
    elif sys.platform == "darwin":
        candidates.append(Path.home() / "Library" / "Application Support" / APP_NAME)
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        if xdg:
            candidates.append(Path(xdg) / APP_NAME)
        candidates.append(Path.home() / ".local" / "share" / APP_NAME)

    candidates.extend([Path.cwd() / ".cheburnet", Path.home() / ".cheburnet"])
    for path in candidates:
        try:
            return _ensure_writable(path)
        except OSError:
            continue
    raise PermissionError("Не удалось найти папку для данных CheburNet.")


def _ensure_writable(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".write_test"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)
    return path


def logs_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def generated_dir() -> Path:
    path = app_data_dir() / "generated"
    path.mkdir(parents=True, exist_ok=True)
    return path


def tools_dir() -> Path:
    path = app_data_dir() / "tools"
    path.mkdir(parents=True, exist_ok=True)
    return path
