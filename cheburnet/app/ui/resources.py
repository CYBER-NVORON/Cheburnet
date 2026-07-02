from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon

from cheburnet.app.core.paths import app_root


def _resource_roots() -> list[Path]:
    roots: list[Path] = []
    bundle = getattr(sys, "_MEIPASS", "")
    if bundle:
        roots.append(Path(bundle))
    root = app_root()
    roots.extend([root, root / "_internal"])
    return roots


def asset_path(*parts: str) -> Path:
    for root in _resource_roots():
        path = root.joinpath("assets", *parts)
        if path.exists():
            return path
    return app_root().joinpath("assets", *parts)


def app_asset_path(*parts: str) -> Path:
    for root in _resource_roots():
        path = root.joinpath("cheburnet", "app", "assets", *parts)
        if path.exists():
            return path
    return Path(__file__).resolve().parents[1].joinpath("assets", *parts)


def app_icon() -> QIcon:
    for name in ("cheburnet.ico", "cheburnet.png"):
        path = asset_path(name)
        if path.exists():
            return QIcon(str(path))
    return QIcon()
