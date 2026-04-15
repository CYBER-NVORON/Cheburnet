from __future__ import annotations

import ipaddress
import json
import os
import re
import subprocess
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from cheburnet.config import app_data_dir

from .system import CREATE_NO_WINDOW, IS_WINDOWS, CommandResult, is_admin, run_command, run_elevated


SING_BOX_RELEASE_API = "https://api.github.com/repos/SagerNet/sing-box/releases/latest"
ZAPRET_DIRECT_DOMAINS = [
    "discord.com",
    ".discord.com",
    "discord.gg",
    ".discord.gg",
    "discordapp.com",
    ".discordapp.com",
    "discordapp.net",
    ".discordapp.net",
    "youtube.com",
    ".youtube.com",
    "youtu.be",
    ".youtu.be",
    "ytimg.com",
    ".ytimg.com",
    "googlevideo.com",
    ".googlevideo.com",
    "ggpht.com",
    ".ggpht.com",
]

Progress = Callable[[str], None]


@dataclass
class SingBoxOperation:
    ok: bool
    message: str
    config_path: str = ""


class SingBoxController:
    def __init__(self) -> None:
        self.process: subprocess.Popen[str] | None = None

    def default_binary_path(self) -> Path:
        return app_data_dir() / "tools" / "sing-box" / "sing-box.exe"

    def default_config_path(self) -> Path:
        return app_data_dir() / "sing-box-config.json"

    def detect_binary(self, configured_path: str = "") -> str | None:
        candidates = []
        if configured_path:
            candidates.append(Path(configured_path))
        candidates.append(self.default_binary_path())
        for directory in os.environ.get("PATH", "").split(os.pathsep):
            candidates.append(Path(directory) / "sing-box.exe")
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None

    def download_latest(self, progress: Progress | None = None) -> Path:
        request = urllib.request.Request(SING_BOX_RELEASE_API, headers={"User-Agent": "Cheburnet/0.1"})
        with urllib.request.urlopen(request, timeout=30) as response:
            release = json.loads(response.read().decode("utf-8"))

        asset = self._pick_windows_asset(release.get("assets", []))
        if not asset:
            raise RuntimeError("В latest release sing-box не найден Windows amd64 zip.")

        tools_dir = self.default_binary_path().parent
        tools_dir.mkdir(parents=True, exist_ok=True)
        archive_path = tools_dir / str(asset["name"])
        if progress:
            progress(f"Скачиваю sing-box: {archive_path.name}")
        urllib.request.urlretrieve(str(asset["browser_download_url"]), archive_path)

        extract_dir = tools_dir / "latest"
        extract_dir.mkdir(parents=True, exist_ok=True)
        if progress:
            progress(f"Распаковываю sing-box в {extract_dir}")
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(extract_dir)

        exe = next(extract_dir.rglob("sing-box.exe"), None)
        if not exe:
            raise RuntimeError("В архиве sing-box не найден sing-box.exe.")
        target = self.default_binary_path()
        target.write_bytes(exe.read_bytes())
        if progress:
            progress(f"sing-box готов: {target}")
        return target

    def generate_config(
        self,
        profile: dict[str, Any],
        bypass_domains: list[str],
        bypass_cidrs: list[str],
        bypass_apps: list[str],
        output_path: str | Path | None = None,
    ) -> Path:
        if str(profile.get("protocol", "")).lower() != "wireguard":
            raise RuntimeError("Точный доменный туннель сейчас доступен только для WireGuard .conf.")
        config_path = Path(str(profile.get("config_path", "")))
        wg = self._parse_wireguard_config(config_path)
        route_domains = self._normalize_domains([*bypass_domains, *ZAPRET_DIRECT_DOMAINS])
        exact_domains = route_domains["domain"]
        suffix_domains = route_domains["domain_suffix"]
        ip_cidrs = self._normalize_cidrs(bypass_cidrs)
        process_names, process_paths = self._normalize_apps(bypass_apps)

        dns_rules: list[dict[str, Any]] = []
        if exact_domains:
            dns_rules.append({"domain": exact_domains, "action": "route", "server": "dns-direct"})
        if suffix_domains:
            dns_rules.append({"domain_suffix": suffix_domains, "action": "route", "server": "dns-direct"})
        if process_names:
            dns_rules.append({"process_name": process_names, "action": "route", "server": "dns-direct"})
        if process_paths:
            dns_rules.append({"process_path": process_paths, "action": "route", "server": "dns-direct"})

        route_rules: list[dict[str, Any]] = [
            {"action": "sniff", "timeout": "1s"},
            {"protocol": "dns", "action": "hijack-dns"},
            {"ip_is_private": True, "action": "route", "outbound": "direct"},
        ]
        if exact_domains:
            route_rules.append({"domain": exact_domains, "action": "route", "outbound": "direct"})
        if suffix_domains:
            route_rules.append({"domain_suffix": suffix_domains, "action": "route", "outbound": "direct"})
        if ip_cidrs:
            route_rules.append({"ip_cidr": ip_cidrs, "action": "route", "outbound": "direct"})
        if process_names:
            route_rules.append({"process_name": process_names, "action": "route", "outbound": "direct"})
        if process_paths:
            route_rules.append({"process_path": process_paths, "action": "route", "outbound": "direct"})

        remote_dns = wg["dns"][0] if wg["dns"] else "1.1.1.1"
        config: dict[str, Any] = {
            "log": {"level": "info", "timestamp": True},
            "dns": {
                "servers": [
                    {
                        "type": "local",
                        "tag": "dns-direct",
                    },
                    {
                        "type": "udp",
                        "tag": "dns-vpn",
                        "server": remote_dns,
                        "server_port": 53,
                        "detour": "vpn",
                    },
                ],
                "rules": dns_rules,
                "final": "dns-vpn",
                "strategy": "ipv4_only",
                "reverse_mapping": True,
            },
            "inbounds": [
                {
                    "type": "tun",
                    "tag": "tun-in",
                    "interface_name": "cheburnet-tun",
                    "address": ["172.19.0.1/30"],
                    "mtu": 1500,
                    "auto_route": True,
                    "strict_route": True,
                    "endpoint_independent_nat": True,
                    "stack": "system",
                }
            ],
            "endpoints": [
                {
                    "type": "wireguard",
                    "tag": "vpn",
                    "system": False,
                    "name": "cheburnet-wg",
                    "mtu": wg["mtu"],
                    "address": wg["address"],
                    "private_key": wg["private_key"],
                    "peers": wg["peers"],
                }
            ],
            "outbounds": [
                {"type": "direct", "tag": "direct"},
                {"type": "block", "tag": "block"},
            ],
            "route": {
                "rules": route_rules,
                "final": "vpn",
                "auto_detect_interface": True,
                "find_process": bool(process_names or process_paths),
                "default_domain_resolver": "dns-direct",
            },
            "experimental": {"cache_file": {"enabled": True}},
        }

        output = Path(output_path) if output_path else self.default_config_path()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        return output

    def check_config(self, binary_path: str, config_path: str | Path) -> CommandResult:
        return run_command([binary_path, "check", "-c", str(config_path)], timeout=30, no_window=False)

    def start(self, binary_path: str, config_path: str | Path) -> SingBoxOperation:
        config = Path(config_path)
        if not config.exists():
            return SingBoxOperation(False, f"Конфиг sing-box не найден: {config}")
        if self.process and self.process.poll() is None:
            return SingBoxOperation(True, "sing-box уже запущен этим приложением.", str(config))

        if IS_WINDOWS and not is_admin():
            run_elevated(binary_path, ["run", "-c", str(config)], cwd=config.parent, show=False)
            return SingBoxOperation(
                True,
                "sing-box запущен через UAC. Логи elevated-процесса недоступны в этом окне.",
                str(config),
            )

        flags = CREATE_NO_WINDOW if IS_WINDOWS else 0
        self.process = subprocess.Popen(
            [binary_path, "run", "-c", str(config)],
            cwd=str(config.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            text=True,
            creationflags=flags,
        )
        return SingBoxOperation(True, "sing-box запущен.", str(config))

    def stop(self) -> SingBoxOperation:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            return SingBoxOperation(True, "sing-box остановлен.")
        if IS_WINDOWS:
            result = run_command(["taskkill", "/IM", "sing-box.exe", "/F"], timeout=15, no_window=False)
            if result.ok:
                return SingBoxOperation(True, "sing-box остановлен через taskkill.")
            if "access is denied" in result.text.lower() or "отказано" in result.text.lower():
                run_elevated("taskkill.exe", ["/IM", "sing-box.exe", "/F"])
                return SingBoxOperation(True, "Останов sing-box отправлен через UAC.")
            return SingBoxOperation(False, result.text or "sing-box не был найден.")
        result = run_command(["pkill", "-f", "sing-box"], timeout=10)
        return SingBoxOperation(result.ok, result.text or "sing-box остановлен.")

    def _parse_wireguard_config(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise RuntimeError(f"WireGuard-конфиг не найден: {path}")

        sections: list[tuple[str, dict[str, str]]] = []
        current_name = ""
        current_data: dict[str, str] = {}
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip().lstrip("\ufeff")
            if not line or line.startswith(("#", ";")):
                continue
            if line.startswith("[") and line.endswith("]"):
                if current_name:
                    sections.append((current_name.lower(), current_data))
                current_name = line[1:-1].strip()
                current_data = {}
                continue
            if "=" not in line or not current_name:
                continue
            key, value = line.split("=", 1)
            current_data[key.strip().lower()] = value.strip()
        if current_name:
            sections.append((current_name.lower(), current_data))

        interface = next((data for name, data in sections if name == "interface"), None)
        peers_raw = [data for name, data in sections if name == "peer"]
        if not interface:
            raise RuntimeError("В WireGuard-конфиге нет секции [Interface].")
        if not peers_raw:
            raise RuntimeError("В WireGuard-конфиге нет секции [Peer].")

        private_key = interface.get("privatekey", "")
        addresses = self._split_csv(interface.get("address", ""))
        if not private_key or not addresses:
            raise RuntimeError("WireGuard-конфиг должен содержать PrivateKey и Address.")

        peers: list[dict[str, Any]] = []
        for peer in peers_raw:
            endpoint = peer.get("endpoint", "")
            public_key = peer.get("publickey", "")
            if not endpoint or not public_key:
                raise RuntimeError("Каждый [Peer] должен содержать PublicKey и Endpoint.")
            host, port = self._parse_endpoint(endpoint)
            item: dict[str, Any] = {
                "address": host,
                "port": port,
                "public_key": public_key,
                "allowed_ips": self._split_csv(peer.get("allowedips", "0.0.0.0/0")),
            }
            if peer.get("presharedkey"):
                item["pre_shared_key"] = peer["presharedkey"]
            if peer.get("persistentkeepalive"):
                item["persistent_keepalive_interval"] = int(peer["persistentkeepalive"])
            peers.append(item)

        mtu = 1408
        if interface.get("mtu"):
            try:
                mtu = int(interface["mtu"])
            except ValueError:
                pass

        return {
            "private_key": private_key,
            "address": addresses,
            "dns": [item for item in self._split_csv(interface.get("dns", "")) if self._is_ip(item)],
            "mtu": mtu,
            "peers": peers,
        }

    @staticmethod
    def _pick_windows_asset(assets: Any) -> dict[str, Any] | None:
        if not isinstance(assets, list):
            return None
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name", "")).lower()
            if name.endswith(".zip") and "windows" in name and ("amd64" in name or "x86_64" in name):
                return asset
        return None

    @staticmethod
    def _split_csv(value: str) -> list[str]:
        return [part.strip() for part in value.split(",") if part.strip()]

    @staticmethod
    def _parse_endpoint(endpoint: str) -> tuple[str, int]:
        endpoint = endpoint.strip()
        if endpoint.startswith("["):
            host, _, rest = endpoint[1:].partition("]")
            port = rest.lstrip(":")
            return host, int(port)
        host, port = endpoint.rsplit(":", 1)
        return host.strip(), int(port)

    @staticmethod
    def _normalize_domains(domains: list[str]) -> dict[str, list[str]]:
        exact: list[str] = []
        suffix: list[str] = []
        for raw in domains:
            text = raw.strip().lower()
            if not text or text.startswith("#"):
                continue
            text = text.removeprefix("*.").strip()
            if "/" in text or "\\" in text:
                continue
            if text.startswith("."):
                value = text
                if value not in suffix:
                    suffix.append(value)
                continue
            if text in {"ru", "рф", "su"}:
                value = f".{text}"
                if value not in suffix:
                    suffix.append(value)
                continue
            if text not in exact:
                exact.append(text)
            value = f".{text}"
            if value not in suffix:
                suffix.append(value)
        return {"domain": exact, "domain_suffix": suffix}

    @staticmethod
    def _normalize_cidrs(cidrs: list[str]) -> list[str]:
        normalized: list[str] = []
        for raw in cidrs:
            text = raw.strip()
            if not text or text.startswith("#"):
                continue
            try:
                value = str(ipaddress.ip_network(text, strict=False))
            except ValueError:
                continue
            if value not in normalized:
                normalized.append(value)
        return normalized

    @staticmethod
    def _normalize_apps(apps: list[str]) -> tuple[list[str], list[str]]:
        names: list[str] = []
        paths: list[str] = []
        for raw in apps:
            text = raw.strip().strip('"')
            if not text or text.startswith("#"):
                continue
            if "\\" in text or "/" in text or text.lower().endswith(".exe"):
                normalized = str(Path(text)) if ("\\" in text or "/" in text) else text
                if "\\" in normalized or "/" in normalized:
                    if normalized not in paths:
                        paths.append(normalized)
                elif normalized not in names:
                    names.append(normalized)
            elif re.match(r"^[\w.-]+$", text) and text not in names:
                names.append(text)
        return names, paths

    @staticmethod
    def _is_ip(value: str) -> bool:
        try:
            ipaddress.ip_address(value)
            return True
        except ValueError:
            return False
