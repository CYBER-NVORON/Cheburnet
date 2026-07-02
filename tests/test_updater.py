from __future__ import annotations

from cheburnet.app.core.updater import SelfUpdateService, is_newer_version, normalize_version


def test_normalize_version_ignores_v_prefix_and_suffix() -> None:
    assert normalize_version("v1.2.3") == (1, 2, 3)
    assert normalize_version("1.2.3-beta") == (1, 2, 3)


def test_is_newer_version_compares_numeric_parts() -> None:
    assert is_newer_version("v0.2.1", "0.2.0") is True
    assert is_newer_version("v0.2.0", "0.2.0") is False
    assert is_newer_version("v0.1.9", "0.2.0") is False


def test_self_update_picks_windows_x64_zip() -> None:
    assets = [
        {"name": "CheburNet-v0.3.0-linux-x64.tar.gz", "browser_download_url": "https://example.com/linux"},
        {"name": "CheburNet-v0.3.0-windows-x64.zip", "browser_download_url": "https://example.com/win"},
    ]

    asset = SelfUpdateService._pick_asset(assets)

    assert asset and asset["browser_download_url"] == "https://example.com/win"
