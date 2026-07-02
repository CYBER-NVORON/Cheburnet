from __future__ import annotations

from copy import deepcopy
from typing import Any

from cheburnet.app.constants import DEFAULT_DIRECT_DOMAINS


DEFAULT_SETTINGS: dict[str, Any] = {
    "theme": "control_deck",
    "accent_color": "#7C5CFF",
    "compact_mode": False,
    "animations": True,
    "start_minimized": False,
    "launch_as_admin": True,
    "selected_profile_id": None,
    "routing_mode": "full_vpn",
    "vpn": {
        "auto_connect": False,
        "auto_failover": False,
        "kill_switch": False,
        "dns_protection": True,
        "tun_mode": True,
    },
    "zapret": {
        "enabled": False,
        "mode": "auto",
        "selected_script": None,
        "install_dir": "",
        "autostart_with_app": False,
    },
    "routing": {
        "direct_domains": list(DEFAULT_DIRECT_DOMAINS),
        "direct_cidrs": [],
    },
}


def default_settings() -> dict[str, Any]:
    return deepcopy(DEFAULT_SETTINGS)
