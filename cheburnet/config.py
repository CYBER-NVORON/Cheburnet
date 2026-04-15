from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


APP_NAME = "Cheburnet"


DEFAULT_SETTINGS: dict[str, Any] = {
    "theme": "dark",
    "zapret_dir": "",
    "selected_zapret_config": "",
    "best_zapret_config": "",
    "last_zapret_results": [],
    "vpn_profiles": [],
    "selected_vpn_profile": "",
    "warp_enabled": False,
    "bypass_domains": [".ru", ".рф", ".su"],
    "bypass_cidrs": [],
    "bypass_apps": [],
    "route_persistent": False,
    "autostart_zapret": False,
    "autostart_vpn": False,
    "autostart_rule_tunnel": False,
    "singbox_path": "",
    "last_singbox_config": "",
    "rule_tunnel_enabled": True,
    "last_applied_routes": [],
    "window_geometry": "1180x760",
}


def app_data_dir() -> Path:
    override = os.environ.get("CHEBURNET_HOME")
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override))
    base = os.environ.get("APPDATA")
    if base:
        candidates.append(Path(base) / APP_NAME)
    candidates.append(Path.cwd() / ".cheburnet")
    candidates.append(Path.home() / ".cheburnet")

    for path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            try:
                probe.unlink(missing_ok=True)
            except OSError:
                pass
            return path
        except OSError:
            continue
    raise PermissionError("Не удалось найти папку для записи настроек Cheburnet.")


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (app_data_dir() / "settings.json")
        self.data: dict[str, Any] = deepcopy(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.save()
            return
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        merged = deepcopy(DEFAULT_SETTINGS)
        if isinstance(loaded, dict):
            merged.update(loaded)
        self.data = merged

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def update(self, values: dict[str, Any]) -> None:
        self.data.update(values)
        self.save()
