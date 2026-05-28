from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RoutingMode(Enum):
    FULL_VPN = "full_vpn"
    ZAPRET_ONLY = "zapret_only"
    SMART_SPLIT = "smart_split"
    CUSTOM_SPLIT = "custom_split"


@dataclass(slots=True)
class Profile:
    id: str
    name: str
    protocol: str
    host: str = ""
    port: int = 0
    country: str = ""
    source: str = "manual"
    raw: str = ""
    outbound: dict[str, Any] = field(default_factory=dict)
    config_path: str = ""
    favorite: bool = False
    latency_ms: int | None = None
    status: str = "unchecked"
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def make_id(cls, value: str) -> str:
        return hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:16]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        return cls(
            id=str(data.get("id") or cls.make_id(str(data))),
            name=str(data.get("name") or "VPN profile"),
            protocol=str(data.get("protocol") or "").lower(),
            host=str(data.get("host") or data.get("server") or ""),
            port=int(data.get("port") or data.get("server_port") or 0),
            country=str(data.get("country") or ""),
            source=str(data.get("source") or "manual"),
            raw=str(data.get("raw") or ""),
            outbound=dict(data.get("outbound") or {}),
            config_path=str(data.get("config_path") or ""),
            favorite=bool(data.get("favorite", False)),
            latency_ms=data.get("latency_ms"),
            status=str(data.get("status") or "unchecked"),
            meta=dict(data.get("meta") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "protocol": self.protocol,
            "host": self.host,
            "port": self.port,
            "country": self.country,
            "source": self.source,
            "raw": self.raw,
            "outbound": self.outbound,
            "config_path": self.config_path,
            "favorite": self.favorite,
            "latency_ms": self.latency_ms,
            "status": self.status,
            "meta": self.meta,
        }

    @property
    def endpoint(self) -> str:
        if self.host and self.port:
            return f"{self.host}:{self.port}"
        return self.host or "не указан"
