from __future__ import annotations

import copy
import ipaddress
import json
import re
from pathlib import Path
from typing import Any

from cheburnet.app.constants import YOUTUBE_DISCORD_DOMAINS
from cheburnet.app.core.paths import generated_dir
from cheburnet.app.errors import ConfigBuildError
from cheburnet.app.models.profile import Profile, RoutingMode
from cheburnet.app.services.wireguard_importer import WireGuardImporter


class SingBoxConfigBuilder:
    def __init__(self, wireguard_importer: WireGuardImporter | None = None) -> None:
        self.wireguard_importer = wireguard_importer or WireGuardImporter()

    def build(
        self,
        profile: Profile,
        settings: dict[str, Any],
        mode: RoutingMode,
        singbox_version: str = "",
        output_path: str | Path | None = None,
    ) -> Path:
        self._require_min_version(singbox_version)
        if mode == RoutingMode.ZAPRET_ONLY:
            raise ConfigBuildError("В режиме Zapret only sing-box не запускается.")

        outbounds: list[dict[str, Any]] = [{"type": "direct", "tag": "direct"}]
        endpoints: list[dict[str, Any]] = []
        final_tag = "proxy"

        if profile.protocol == "wireguard":
            self._require_wireguard_endpoint_support(singbox_version)
            wg_config = self._wireguard_config(profile)
            endpoints.append(self.wireguard_importer.endpoint_dict(wg_config))
            final_tag = "vpn"
        else:
            if not profile.outbound:
                raise ConfigBuildError("У профиля нет outbound-конфигурации sing-box.")
            outbound = copy.deepcopy(profile.outbound)
            outbound["tag"] = "proxy"
            outbounds.insert(0, outbound)

        direct_domains = self._direct_domains(settings, mode)
        exact_domains, suffix_domains = self._normalize_domains(direct_domains)
        rules = self._route_rules(exact_domains, suffix_domains, settings.get("routing", {}).get("direct_cidrs", []))
        dns_rules = self._dns_rules(exact_domains, suffix_domains)
        config: dict[str, Any] = {
            "log": {"level": "info", "timestamp": True},
            "dns": {
                "servers": [
                    {"type": "local", "tag": "dns-direct"},
                ],
                "rules": dns_rules,
                "final": "dns-direct",
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
                    "strict_route": bool(settings.get("vpn", {}).get("dns_protection", True) or settings.get("vpn", {}).get("kill_switch", False)),
                    "stack": "system",
                }
            ],
            "outbounds": outbounds,
            "route": {
                "rules": rules,
                "final": final_tag,
                "auto_detect_interface": True,
                "default_domain_resolver": "dns-direct",
            },
            "experimental": {"cache_file": {"enabled": True}},
        }
        if endpoints:
            config["endpoints"] = endpoints

        output = Path(output_path) if output_path else generated_dir() / "singbox_config.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        return output

    def build_probe_config(self, profile: Profile, listen_port: int, output_path: str | Path) -> Path:
        if not profile.outbound:
            raise ConfigBuildError("Проверка через локальный proxy доступна только для proxy-профилей.")
        outbound = copy.deepcopy(profile.outbound)
        outbound["tag"] = "proxy"
        config = {
            "log": {"level": "warn", "timestamp": True},
            "dns": {"servers": [{"type": "local", "tag": "dns-direct"}], "final": "dns-direct"},
            "inbounds": [{"type": "mixed", "tag": "mixed-in", "listen": "127.0.0.1", "listen_port": listen_port}],
            "outbounds": [outbound, {"type": "direct", "tag": "direct"}],
            "route": {"final": "proxy", "default_domain_resolver": "dns-direct"},
        }
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        return output

    @staticmethod
    def _require_min_version(version: str) -> None:
        if not version:
            return
        parsed = SingBoxConfigBuilder._parse_version(version)
        if parsed and parsed < (1, 11, 0):
            raise ConfigBuildError("Эта версия sing-box слишком старая для CheburNet TUN. Обновите sing-box до 1.11.0 или новее.")

    @staticmethod
    def _require_wireguard_endpoint_support(version: str) -> None:
        if not version:
            return
        parsed = SingBoxConfigBuilder._parse_version(version)
        if parsed and parsed < (1, 11, 0):
            raise ConfigBuildError("Эта версия sing-box не поддерживает выбранный WireGuard-режим.")

    def _wireguard_config(self, profile: Profile):
        embedded = profile.meta.get("wireguard") if isinstance(profile.meta, dict) else None
        if isinstance(embedded, dict):
            config = self.wireguard_importer.config_from_dict(embedded)
            if config.private_key and config.address and config.peers:
                return config
        if profile.config_path:
            return self.wireguard_importer.parse(profile.config_path)
        raise ConfigBuildError("В WireGuard профиле нет сохраненных данных конфигурации.")

    @staticmethod
    def _parse_version(version: str) -> tuple[int, int, int] | None:
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", version)
        if not match:
            return None
        return tuple(int(part) for part in match.groups())

    @staticmethod
    def _direct_domains(settings: dict[str, Any], mode: RoutingMode) -> list[str]:
        routing = settings.get("routing", {}) if isinstance(settings.get("routing"), dict) else {}
        vpn = settings.get("vpn", {}) if isinstance(settings.get("vpn"), dict) else {}
        domains = [] if vpn.get("kill_switch") else list(routing.get("direct_domains", []))
        if mode == RoutingMode.SMART_SPLIT:
            domains.extend(YOUTUBE_DISCORD_DOMAINS)
        return domains

    @classmethod
    def _route_rules(cls, exact: list[str], suffix: list[str], cidrs: list[str]) -> list[dict[str, Any]]:
        rules: list[dict[str, Any]] = [
            {"action": "sniff", "timeout": "1s"},
            {"protocol": "dns", "action": "hijack-dns"},
            {"ip_is_private": True, "action": "route", "outbound": "direct"},
        ]
        if exact:
            rules.append({"domain": exact, "action": "route", "outbound": "direct"})
        if suffix:
            rules.append({"domain_suffix": suffix, "action": "route", "outbound": "direct"})
        normalized_cidrs = cls._normalize_cidrs(cidrs)
        if normalized_cidrs:
            rules.append({"ip_cidr": normalized_cidrs, "action": "route", "outbound": "direct"})
        return rules

    @staticmethod
    def _dns_rules(exact: list[str], suffix: list[str]) -> list[dict[str, Any]]:
        rules: list[dict[str, Any]] = []
        if exact:
            rules.append({"domain": exact, "action": "route", "server": "dns-direct"})
        if suffix:
            rules.append({"domain_suffix": suffix, "action": "route", "server": "dns-direct"})
        return rules

    @staticmethod
    def _normalize_domains(domains: list[str]) -> tuple[list[str], list[str]]:
        exact: list[str] = []
        suffix: list[str] = []
        for raw in domains:
            text = str(raw).strip().lower()
            if not text or text.startswith("#"):
                continue
            text = text.removeprefix("*.").strip()
            if "/" in text or "\\" in text:
                continue
            if text == "сђс„":
                text = "рф"
            if text.startswith(".сђс„"):
                text = ".рф"
            if text.startswith(".") or text in {"ru", "рф", "su"}:
                value = text if text.startswith(".") else f".{text}"
                if value not in suffix:
                    suffix.append(value)
                continue
            if text not in exact:
                exact.append(text)
            suffixed = f".{text}"
            if suffixed not in suffix:
                suffix.append(suffixed)
        return exact, suffix

    @staticmethod
    def _normalize_cidrs(cidrs: list[str]) -> list[str]:
        result: list[str] = []
        for raw in cidrs:
            try:
                value = str(ipaddress.ip_network(str(raw).strip(), strict=False))
            except ValueError:
                continue
            if value not in result:
                result.append(value)
        return result
