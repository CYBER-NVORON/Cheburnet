from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cheburnet.app.errors import ProfileImportError
from cheburnet.app.models.profile import Profile


@dataclass(slots=True)
class WireGuardPeer:
    address: str
    port: int
    public_key: str
    allowed_ips: list[str]
    pre_shared_key: str = ""
    persistent_keepalive_interval: int | None = None


@dataclass(slots=True)
class WireGuardConfig:
    private_key: str
    address: list[str]
    dns: list[str]
    mtu: int
    peers: list[WireGuardPeer]


class WireGuardImporter:
    def import_file(self, path: str | Path) -> Profile:
        config_path = Path(path)
        text = config_path.read_text(encoding="utf-8", errors="replace")
        parsed = self.parse_text(text)
        first_peer = parsed.peers[0]
        name = config_path.stem or "WireGuard"
        profile = Profile(
            id=Profile.make_id(f"wireguard:{text}"),
            name=name,
            protocol="wireguard",
            host=first_peer.address,
            port=first_peer.port,
            source="wireguard",
            config_path="",
            status="unchecked",
            meta={
                "original_file": str(config_path),
                "wireguard": self.config_to_dict(parsed),
                "address": parsed.address,
                "dns": parsed.dns,
                "peers": len(parsed.peers),
            },
        )
        return profile

    def parse(self, path: str | Path) -> WireGuardConfig:
        config_path = Path(path)
        if not config_path.exists():
            raise ProfileImportError(f"WireGuard .conf не найден: {config_path}")
        return self.parse_text(config_path.read_text(encoding="utf-8", errors="replace"))

    def parse_text(self, text: str) -> WireGuardConfig:
        sections: list[tuple[str, dict[str, str]]] = []
        current_name = ""
        current: dict[str, str] = {}
        for raw in text.splitlines():
            line = raw.strip().lstrip("\ufeff")
            if not line or line.startswith(("#", ";")):
                continue
            if line.startswith("[") and line.endswith("]"):
                if current_name:
                    sections.append((current_name.lower(), current))
                current_name = line[1:-1].strip()
                current = {}
                continue
            if "=" not in line or not current_name:
                continue
            key, value = line.split("=", 1)
            current[key.strip().lower()] = value.strip()
        if current_name:
            sections.append((current_name.lower(), current))

        interface = next((data for name, data in sections if name == "interface"), None)
        peers_raw = [data for name, data in sections if name == "peer"]
        if not interface:
            raise ProfileImportError("В WireGuard .conf нет секции [Interface].")
        if not peers_raw:
            raise ProfileImportError("В WireGuard .conf нет секции [Peer].")

        private_key = interface.get("privatekey", "")
        address = self._split_csv(interface.get("address", ""))
        if not private_key:
            raise ProfileImportError("В [Interface] отсутствует PrivateKey.")
        if not address:
            raise ProfileImportError("В [Interface] отсутствует Address.")

        peers: list[WireGuardPeer] = []
        for peer in peers_raw:
            public_key = peer.get("publickey", "")
            endpoint = peer.get("endpoint", "")
            allowed_ips = self._split_csv(peer.get("allowedips", ""))
            if not public_key:
                raise ProfileImportError("В [Peer] отсутствует PublicKey.")
            if not endpoint:
                raise ProfileImportError("В [Peer] отсутствует Endpoint.")
            if not allowed_ips:
                raise ProfileImportError("В [Peer] отсутствует AllowedIPs.")
            host, port = self._parse_endpoint(endpoint)
            keepalive = None
            if peer.get("persistentkeepalive"):
                try:
                    keepalive = int(peer["persistentkeepalive"])
                except ValueError:
                    keepalive = None
            peers.append(
                WireGuardPeer(
                    address=host,
                    port=port,
                    public_key=public_key,
                    allowed_ips=allowed_ips,
                    pre_shared_key=peer.get("presharedkey", ""),
                    persistent_keepalive_interval=keepalive,
                )
            )

        mtu = 1408
        if interface.get("mtu"):
            try:
                mtu = int(interface["mtu"])
            except ValueError:
                pass

        return WireGuardConfig(
            private_key=private_key,
            address=address,
            dns=self._split_csv(interface.get("dns", "")),
            mtu=mtu,
            peers=peers,
        )

    @staticmethod
    def config_to_dict(config: WireGuardConfig) -> dict[str, Any]:
        return {
            "private_key": config.private_key,
            "address": list(config.address),
            "dns": list(config.dns),
            "mtu": config.mtu,
            "peers": [
                {
                    "address": peer.address,
                    "port": peer.port,
                    "public_key": peer.public_key,
                    "allowed_ips": list(peer.allowed_ips),
                    "pre_shared_key": peer.pre_shared_key,
                    "persistent_keepalive_interval": peer.persistent_keepalive_interval,
                }
                for peer in config.peers
            ],
        }

    @staticmethod
    def config_from_dict(data: dict[str, Any]) -> WireGuardConfig:
        peers = [
            WireGuardPeer(
                address=str(peer.get("address") or ""),
                port=int(peer.get("port") or 0),
                public_key=str(peer.get("public_key") or ""),
                allowed_ips=[str(item) for item in peer.get("allowed_ips", [])],
                pre_shared_key=str(peer.get("pre_shared_key") or ""),
                persistent_keepalive_interval=(
                    int(peer["persistent_keepalive_interval"])
                    if peer.get("persistent_keepalive_interval") is not None
                    else None
                ),
            )
            for peer in data.get("peers", [])
            if isinstance(peer, dict)
        ]
        return WireGuardConfig(
            private_key=str(data.get("private_key") or ""),
            address=[str(item) for item in data.get("address", [])],
            dns=[str(item) for item in data.get("dns", [])],
            mtu=int(data.get("mtu") or 1408),
            peers=peers,
        )

    @staticmethod
    def endpoint_dict(config: WireGuardConfig) -> dict[str, Any]:
        peers: list[dict[str, Any]] = []
        for peer in config.peers:
            item: dict[str, Any] = {
                "address": peer.address,
                "port": peer.port,
                "public_key": peer.public_key,
                "allowed_ips": peer.allowed_ips,
            }
            if peer.pre_shared_key:
                item["pre_shared_key"] = peer.pre_shared_key
            if peer.persistent_keepalive_interval is not None:
                item["persistent_keepalive_interval"] = peer.persistent_keepalive_interval
            peers.append(item)
        return {
            "type": "wireguard",
            "tag": "vpn",
            "system": False,
            "name": "cheburnet-wg",
            "mtu": config.mtu,
            "address": config.address,
            "private_key": config.private_key,
            "peers": peers,
        }

    @staticmethod
    def _split_csv(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @staticmethod
    def _parse_endpoint(endpoint: str) -> tuple[str, int]:
        text = endpoint.strip()
        if text.startswith("["):
            host, _, rest = text[1:].partition("]")
            port = rest.lstrip(":")
            if not host or not port:
                raise ProfileImportError(f"Некорректный Endpoint: {endpoint}")
            return host, int(port)
        if ":" not in text:
            raise ProfileImportError(f"Некорректный Endpoint: {endpoint}")
        host, port = text.rsplit(":", 1)
        return host.strip(), int(port)
