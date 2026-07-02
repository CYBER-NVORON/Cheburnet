from __future__ import annotations

import json

from cheburnet.app.core.config import SettingsStore


def test_settings_store_keeps_default_shape_for_legacy_sections(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"free_configs": [], "vpn": {"auto_connect": True}}, ensure_ascii=False), encoding="utf-8")

    store = SettingsStore(path)

    assert store.section("vpn")["auto_connect"] is True
    assert "free_configs" not in store.data
    assert store.section("free_configs") == {}


def test_settings_store_drops_legacy_profile_lists(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"free_configs": {"sources": ["https://example.com/profiles.txt"]}}, ensure_ascii=False),
        encoding="utf-8",
    )

    store = SettingsStore(path)

    assert "free_configs" not in store.data
    assert "free_configs" not in json.loads(path.read_text(encoding="utf-8"))
