from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class HealthStatus(Enum):
    UNCHECKED = "unchecked"
    CHECKING = "checking"
    OK = "ok"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass(slots=True)
class HealthCheckResult:
    target: str
    status: HealthStatus
    detail: str = ""
    latency_ms: int | None = None
