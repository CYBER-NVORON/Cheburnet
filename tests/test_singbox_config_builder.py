from __future__ import annotations

import json

import pytest

from cheburnet.app.errors import ConfigBuildError
from cheburnet.app.models.profile import Profile, RoutingMode
from cheburnet.app.models.settings import default_settings
from cheburnet.app.services.singbox_config_builder import SingBoxConfigBuilder
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


def test_builder_generates_tun_proxy_config_with_smart_split(tmp_path) -> None:
    profile = Profile(
        id="p1",
        name="Proxy",
        protocol="vless",
        host="example.com",
        port=443,
        outbound={"type": "vless", "server": "example.com", "server_port": 443, "uuid": "123e4567-e89b-12d3-a456-426614174000"},
    )

    path = SingBoxConfigBuilder().build(profile, default_settings(), RoutingMode.SMART_SPLIT, "1.14.0", tmp_path / "config.json")
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["inbounds"][0]["type"] == "tun"
    assert data["dns"]["reverse_mapping"] is True
    assert data["route"]["auto_detect_interface"] is True
    assert data["route"]["final"] == "proxy"
    assert any(".youtube.com" in rule.get("domain_suffix", []) for rule in data["route"]["rules"])
    assert not any(outbound.get("type") == "block" for outbound in data["outbounds"])


def test_builder_rejects_old_wireguard_endpoint_version(tmp_path) -> None:
    profile = Profile(id="wg", name="WG", protocol="wireguard", config_path=str(tmp_path / "client.conf"))

    with pytest.raises(ConfigBuildError):
        SingBoxConfigBuilder().build(profile, default_settings(), RoutingMode.FULL_VPN, "1.10.0", tmp_path / "config.json")


def test_builder_uses_embedded_wireguard_config_after_source_file_deleted(tmp_path) -> None:
    source = tmp_path / "client.conf"
    source.write_text(WG_CONF, encoding="utf-8")
    profile = WireGuardImporter().import_file(source)
    source.unlink()

    path = SingBoxConfigBuilder().build(profile, default_settings(), RoutingMode.FULL_VPN, "1.14.0", tmp_path / "config.json")
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["endpoints"][0]["type"] == "wireguard"
    assert data["endpoints"][0]["private_key"] == "private-key-value"
    assert data["endpoints"][0]["peers"][0]["address"] == "wg.example.com"
