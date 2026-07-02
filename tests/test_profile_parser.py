from __future__ import annotations

import base64
import json

from cheburnet.app.services.free_configs_service import FreeConfigsService


def test_parse_vless_uri() -> None:
    service = FreeConfigsService()

    profile = service.parse_link("vless://123e4567-e89b-12d3-a456-426614174000@example.com:443?security=tls&type=ws&path=%2Fws#Test")

    assert profile is not None
    assert profile.protocol == "vless"
    assert profile.host == "example.com"
    assert profile.port == 443
    assert profile.outbound["transport"]["type"] == "ws"


def test_parse_vmess_uri() -> None:
    service = FreeConfigsService()
    payload = {
        "ps": "VMess Test",
        "add": "vmess.example",
        "port": "443",
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "scy": "auto",
        "net": "tcp",
        "tls": "tls",
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")

    profile = service.parse_link(f"vmess://{encoded}")

    assert profile is not None
    assert profile.name == "VMess Test"
    assert profile.protocol == "vmess"
    assert profile.outbound["tls"]["enabled"] is True

