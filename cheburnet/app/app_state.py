from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QObject, Signal

from cheburnet.app.models.health import HealthCheckResult, HealthStatus
from cheburnet.app.models.profile import Profile, RoutingMode
from cheburnet.app.models.vpn_status import VpnStatus
from cheburnet.app.models.zapret_status import ZapretStatus


class AppState(QObject):
    vpn_status_changed = Signal(object)
    zapret_status_changed = Signal(object)
    servers_changed = Signal(list)
    selected_profile_changed = Signal(object)
    traffic_changed = Signal(object)
    routes_changed = Signal(dict)
    health_changed = Signal(str, object)
    log_added = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.is_admin = False
        self.vpn_status = VpnStatus.DISCONNECTED
        self.zapret_status = ZapretStatus.NOT_INSTALLED
        self.routing_mode = RoutingMode.FULL_VPN
        self.selected_profile: Profile | None = None
        self.servers: list[Profile] = []
        self.traffic: dict[str, Any] = {"download_mbps": 0.0, "upload_mbps": 0.0, "points": []}
        self.routes: dict[str, str] = {"youtube": "VPN", "discord": "VPN", "other": "VPN"}
        self.health: dict[str, HealthCheckResult] = {
            "youtube": HealthCheckResult("youtube", HealthStatus.UNCHECKED),
            "discord": HealthCheckResult("discord", HealthStatus.UNCHECKED),
        }
        self.logs: list[str] = []
        self.last_error = ""
        self.connected_since: float | None = None

    def set_admin(self, value: bool) -> None:
        self.is_admin = value

    def set_vpn_status(self, status: VpnStatus, error: str = "") -> None:
        if status == VpnStatus.CONNECTED and self.connected_since is None:
            self.connected_since = time.time()
        if status in {VpnStatus.DISCONNECTED, VpnStatus.ERROR}:
            self.connected_since = None
        self.last_error = error
        if self.vpn_status == status and not error:
            return
        self.vpn_status = status
        self.vpn_status_changed.emit(status)

    def set_zapret_status(self, status: ZapretStatus, error: str = "") -> None:
        self.last_error = error
        if self.zapret_status == status and not error:
            return
        self.zapret_status = status
        self.zapret_status_changed.emit(status)

    def set_servers(self, servers: list[Profile]) -> None:
        self.servers = list(servers)
        self.servers_changed.emit(self.servers)

    def set_selected_profile(self, profile: Profile | None) -> None:
        self.selected_profile = profile
        self.selected_profile_changed.emit(profile)

    def set_traffic(self, traffic: dict[str, Any]) -> None:
        self.traffic = dict(traffic)
        self.traffic_changed.emit(self.traffic)

    def set_routes(self, routes: dict[str, str]) -> None:
        self.routes = dict(routes)
        self.routes_changed.emit(self.routes)

    def set_health(self, service: str, result: HealthCheckResult) -> None:
        self.health[service] = result
        self.health_changed.emit(service, result)

    def add_log(self, message: str) -> None:
        message = str(message).rstrip()
        if not message:
            return
        if len(message) >= 8 and message[2:3] == ":" and message[5:6] == ":":
            line = message
        else:
            line = f"{time.strftime('%H:%M:%S')}  {message}"
        self.logs.append(line)
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]
        self.log_added.emit(line)

    def clear_logs(self) -> None:
        self.logs.clear()
