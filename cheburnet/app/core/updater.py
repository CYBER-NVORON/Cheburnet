from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class VersionInfo:
    name: str
    current: str
    latest: str
    detail: str = ""
