from __future__ import annotations

import pytest

from cheburnet.app.errors import ProfileImportError
from cheburnet.app.services.wireguard_importer import WireGuardImporter


WG_CONF = """
[Interface]
PrivateKey = private-key-value
Address = 10.0.0.2/32
DNS = 1.1.1.1

[Peer]
PublicKey = public-key-value
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = wg.example.com:51820
PersistentKeepalive = 25
"""


def test_wireguard_importer_stores_parsed_config_in_profile(tmp_path) -> None:
    path = tmp_path / "client.conf"
    path.write_text(WG_CONF, encoding="utf-8")

    profile = WireGuardImporter().import_file(path)

    assert profile.protocol == "wireguard"
    assert profile.host == "wg.example.com"
    assert profile.port == 51820
    assert profile.config_path == ""
    assert profile.meta["original_file"] == str(path)
    assert profile.meta["wireguard"]["private_key"] == "private-key-value"


def test_wireguard_imported_profile_survives_deleted_source_file(tmp_path) -> None:
    path = tmp_path / "client.conf"
    path.write_text(WG_CONF, encoding="utf-8")

    profile = WireGuardImporter().import_file(path)
    path.unlink()
    restored = WireGuardImporter.config_from_dict(profile.meta["wireguard"])

    assert restored.private_key == "private-key-value"
    assert restored.peers[0].address == "wg.example.com"


def test_wireguard_importer_requires_allowed_ips(tmp_path) -> None:
    path = tmp_path / "bad.conf"
    path.write_text(WG_CONF.replace("AllowedIPs = 0.0.0.0/0, ::/0", ""), encoding="utf-8")

    with pytest.raises(ProfileImportError):
        WireGuardImporter().parse(path)
