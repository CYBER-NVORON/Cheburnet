from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ServerCheck:
    profile_id: str
    status: str = "unchecked"
    latency_ms: int | None = None
    detail: str = ""
