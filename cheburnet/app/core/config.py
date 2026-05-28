from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from cheburnet.app.core.paths import app_data_dir
from cheburnet.app.models.settings import default_settings


def _deep_merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in incoming.items():
        current = result.get(key)
        if isinstance(current, dict):
            if isinstance(value, dict):
                result[key] = _deep_merge(current, value)
            continue
        else:
            result[key] = value
    return result


def _drop_legacy_default_sources(data: dict[str, Any]) -> None:
    free_configs = data.get("free_configs")
    if not isinstance(free_configs, dict):
        return
    sources = free_configs.get("sources")
    if not isinstance(sources, list):
        return
    legacy_repo = "goida" + "-vpn-configs"
    free_configs["sources"] = [
        source
        for source in sources
        if not (legacy_repo in str(source) and "githubmirror" in str(source))
    ]


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or app_data_dir() / "settings.json"
        self.data = default_settings()
        self.load()

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            self.save()
            return self.data
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        self.data = _deep_merge(default_settings(), loaded if isinstance(loaded, dict) else {})
        _drop_legacy_default_sources(self.data)
        return self.data

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def section(self, key: str) -> dict[str, Any]:
        value = self.data.get(key)
        return value if isinstance(value, dict) else {}

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def update(self, values: dict[str, Any]) -> None:
        self.data = _deep_merge(self.data, values)
        self.save()
