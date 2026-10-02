from __future__ import annotations

import copy
import ipaddress
import json
from pathlib import Path
from typing import Any

from cheburnet.app.constants import YOUTUBE_DISCORD_DOMAINS
from cheburnet.app.core.paths import generated_dir
from cheburnet.app.errors import ConfigBuildError
from cheburnet.app.models.profile import Profile
from cheburnet.app.services.wireguard_importer import WireGuardImporter


class MihomoConfigBuilder:
    def __init__(self) -> None:
        self.wireguard_importer = WireGuardImporter()

    def build_config(self, profile: Profile, settings: dict[str, Any], output_path: str | Path | None = None) -> Path:
        mode = settings.get("routing_mode", "smart_split")
        
        proxy = None
        if profile.protocol == "wireguard":
            wg_config = self._wireguard_config(profile)
            proxy = self.wireguard_importer.proxy_dict(wg_config)
            proxy["name"] = "proxy"
        else:
            if not profile.outbound:
                raise ConfigBuildError("Profile proxy configuration is missing.")
            proxy = copy.deepcopy(profile.outbound)
            proxy["name"] = "proxy"

        direct_domains = self._direct_domains(settings, mode)
        exact_domains, suffix_domains = self._normalize_domains(direct_domains)
        cidrs = self._normalize_cidrs(settings.get("routing", {}).get("direct_cidrs", []))

        rules = []
        if exact_domains:
            for d in exact_domains:
                rules.append(f"DOMAIN,{d},DIRECT")
        if suffix_domains:
            for d in suffix_domains:
                rules.append(f"DOMAIN-SUFFIX,{d.lstrip('.')},DIRECT")
        if cidrs:
            for c in cidrs:
                rules.append(f"IP-CIDR,{c},DIRECT")
        
        rules.append("MATCH,proxy")

        config = {
            "mode": "rule",
            "log-level": "warning",
            "ipv6": True,
            "allow-lan": False,
            "tcp-concurrent": True,
            "dns": {
                "enable": True,
                "listen": "127.0.0.1:1053",
                "enhanced-mode": "fake-ip",
                "fake-ip-range": "198.18.0.1/16",
                "nameserver": ["8.8.8.8", "1.1.1.1"],
                "fallback": ["1.0.0.1", "8.8.4.4"]
            },
            "tun": {
                "enable": True,
                "stack": "system",
                "auto-route": True,
                "auto-detect-interface": True,
                "dns-hijack": ["any:53"],
                "strict-route": bool(settings.get("vpn", {}).get("dns_protection", True) or settings.get("vpn", {}).get("kill_switch", False))
            },
            "proxies": [proxy],
            "rules": rules
        }

        output = Path(output_path) if output_path else generated_dir() / "config.yaml"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        return output

    def build_probe_config(self, profile: Profile, listen_port: int, output_path: str | Path) -> Path:
        if not profile.outbound:
            raise ConfigBuildError("Profile proxy configuration is missing.")
        proxy = copy.deepcopy(profile.outbound)
        proxy["name"] = "proxy"
        config = {
            "mode": "rule",
            "log-level": "warning",
            "allow-lan": True,
            "mixed-port": listen_port,
            "proxies": [proxy],
            "rules": ["MATCH,proxy"]
        }
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        return output

    def _wireguard_config(self, profile: Profile):
        embedded = profile.meta.get("wireguard") if isinstance(profile.meta, dict) else None
        if isinstance(embedded, dict):
            config = self.wireguard_importer.config_from_dict(embedded)
            if config.private_key and config.address and config.peers:
                return config
        if profile.config_path:
            return self.wireguard_importer.parse(profile.config_path)
        raise ConfigBuildError("WireGuard profile is broken.")

    @staticmethod
    def _direct_domains(settings: dict[str, Any], mode: str) -> list[str]:
        routing = settings.get("routing", {}) if isinstance(settings.get("routing"), dict) else {}
        vpn = settings.get("vpn", {}) if isinstance(settings.get("vpn"), dict) else {}
        if vpn.get("kill_switch") or mode == "full_vpn":
            return []
        domains = list(routing.get("direct_domains", []))
        if mode == "smart_split":
            domains.extend(YOUTUBE_DISCORD_DOMAINS)
        return domains

    @staticmethod
    def _normalize_domains(domains: list[str]) -> tuple[list[str], list[str]]:
        exact: list[str] = []
        suffix: list[str] = []
        for raw in domains:
            text = str(raw).strip().lower()
            if not text or text.startswith("#"): continue
            text = text.removeprefix("*.").strip()
            if "/" in text or "\\" in text: continue
            if text == "рф": text = "xn--p1ai"
            if text.startswith(".рф"): text = ".xn--p1ai"
            if text.startswith(".") or text in {"ru", "xn--p1ai", "su"}:
                value = text if text.startswith(".") else f".{text}"
                if value not in suffix: suffix.append(value)
                continue
            if text not in exact: exact.append(text)
            suffixed = f".{text}"
            if suffixed not in suffix: suffix.append(suffixed)
        return exact, suffix

    @staticmethod
    def _normalize_cidrs(cidrs: list[str]) -> list[str]:
        result: list[str] = []
        for raw in cidrs:
            try:
                value = str(ipaddress.ip_network(str(raw).strip(), strict=False))
            except ValueError:
                continue
            if value not in result: result.append(value)
        return result
