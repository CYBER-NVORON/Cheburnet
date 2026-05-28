from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon

from cheburnet.app.core.paths import app_root


def asset_path(*parts: str) -> Path:
    return app_root().joinpath("assets", *parts)


def app_icon() -> QIcon:
    for name in ("cheburnet.ico", "cheburnet.png"):
        path = asset_path(name)
        if path.exists():
            return QIcon(str(path))
    return QIcon()
