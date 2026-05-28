from __future__ import annotations

import json

from cheburnet.app.core.config import SettingsStore


def test_settings_store_keeps_default_shape_for_legacy_sections(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"free_configs": [], "vpn": {"auto_connect": True}}, ensure_ascii=False), encoding="utf-8")

    store = SettingsStore(path)

    assert isinstance(store.section("free_configs"), dict)
    assert store.section("vpn")["auto_connect"] is True
    assert store.section("free_configs")["enabled"] is True


def test_settings_store_drops_legacy_builtin_sources(tmp_path) -> None:
    path = tmp_path / "settings.json"
    legacy = "https://raw.githubusercontent.com/AvenCores/goida-vpn-configs/main/githubmirror/1.txt"
    custom = "https://example.com/profiles.txt"
    path.write_text(
        json.dumps({"free_configs": {"sources": [legacy, custom]}}, ensure_ascii=False),
        encoding="utf-8",
    )

    store = SettingsStore(path)

    assert store.section("free_configs")["sources"] == [custom]
