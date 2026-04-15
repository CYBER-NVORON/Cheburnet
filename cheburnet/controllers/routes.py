from __future__ import annotations

import ipaddress
import json
import socket
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from cheburnet.config import app_data_dir

from .system import IS_WINDOWS, CommandResult, run_command


RIPE_DELEGATED_URL = "https://ftp.ripe.net/pub/stats/ripencc/delegated-ripencc-latest"
Progress = Callable[[str], None]


@dataclass
class RouteTarget:
    cidr: str
    source: str


@dataclass
class DefaultGateway:
    interface_index: int
    next_hop: str


class RouteManager:
    def __init__(self) -> None:
        self.cache_dir = app_data_dir() / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def download_ru_ipv4(self, progress: Progress | None = None) -> list[str]:
        if progress:
            progress("Загружаю IPv4-диапазоны RU из RIPE delegated stats...")
        request = urllib.request.Request(RIPE_DELEGATED_URL, headers={"User-Agent": "Cheburnet/0.1"})
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read().decode("utf-8", errors="replace")

        cidrs: list[str] = []
        for line in raw.splitlines():
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) < 7:
                continue
            _registry, country, kind, start, value, _date, status = parts[:7]
            if country != "RU" or kind != "ipv4" or status not in {"allocated", "assigned"}:
                continue
            count = int(value)
            first = ipaddress.IPv4Address(start)
            last = ipaddress.IPv4Address(int(first) + count - 1)
            cidrs.extend(str(network) for network in ipaddress.summarize_address_range(first, last))

        cache_file = self.cache_dir / "ru_ipv4.txt"
        cache_file.write_text("\n".join(cidrs), encoding="utf-8")
        if progress:
            progress(f"Сохранено {len(cidrs)} RU IPv4 сетей: {cache_file}")
        return cidrs

    def load_cached_ru_ipv4(self) -> list[str]:
        cache_file = self.cache_dir / "ru_ipv4.txt"
        if not cache_file.exists():
            return []
        return [line.strip() for line in cache_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    def resolve_targets(self, domains: Iterable[str], cidrs: Iterable[str], progress: Progress | None = None) -> list[RouteTarget]:
        targets: list[RouteTarget] = []
        for item in cidrs:
            text = item.strip()
            if not text:
                continue
            try:
                network = ipaddress.ip_network(text, strict=False)
            except ValueError:
                if progress:
                    progress(f"Пропускаю некорректный CIDR: {text}")
                continue
            if isinstance(network, ipaddress.IPv4Network):
                targets.append(RouteTarget(str(network), text))

        for domain in domains:
            host = domain.strip()
            if not host or host.startswith("."):
                continue
            try:
                infos = socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM)
            except socket.gaierror as exc:
                if progress:
                    progress(f"DNS не разрешил {host}: {exc}")
                continue
            ips = sorted({info[4][0] for info in infos})
            for ip in ips:
                targets.append(RouteTarget(f"{ip}/32", host))
        return self._unique_targets(targets)

    def apply_routes(
        self,
        targets: Iterable[RouteTarget],
        persistent: bool = False,
        progress: Progress | None = None,
    ) -> list[RouteTarget]:
        if not IS_WINDOWS:
            raise RuntimeError("Автоматическое добавление маршрутов сейчас реализовано только для Windows.")
        gateway = self.default_gateway()
        applied: list[RouteTarget] = []
        for target in targets:
            destination, mask = self._cidr_to_route(target.cidr)
            command = ["route"]
            if persistent:
                command.append("-p")
            command.extend(["add", destination, "mask", mask, gateway.next_hop, "metric", "1", "IF", str(gateway.interface_index)])
            result = run_command(command, timeout=15, no_window=False)
            already_exists = "object already exists" in result.text.lower() or "уже существует" in result.text.lower()
            if result.ok or already_exists:
                applied.append(target)
                if progress:
                    progress(f"Маршрут активен: {target.cidr} -> {gateway.next_hop}")
            else:
                if progress:
                    progress(f"Не удалось добавить {target.cidr}: {result.text}")
        return applied

    def remove_routes(self, targets: Iterable[RouteTarget], progress: Progress | None = None) -> None:
        if not IS_WINDOWS:
            return
        for target in targets:
            destination, mask = self._cidr_to_route(target.cidr)
            result = run_command(["route", "delete", destination, "mask", mask], timeout=10, no_window=False)
            if progress:
                status = "удалён" if result.ok else "не удалён"
                progress(f"Маршрут {status}: {target.cidr}")

    def default_gateway(self) -> DefaultGateway:
        if not IS_WINDOWS:
            raise RuntimeError("Определение default gateway сейчас реализовано только для Windows.")
        ps = (
            "$routes = Get-NetRoute -DestinationPrefix '0.0.0.0/0' | "
            "Where-Object { $_.NextHop -ne '0.0.0.0' } | "
            "Sort-Object RouteMetric,InterfaceMetric | "
            "ForEach-Object { "
            "$adapter = Get-NetAdapter -InterfaceIndex $_.InterfaceIndex -ErrorAction SilentlyContinue; "
            "[PSCustomObject]@{InterfaceIndex=$_.InterfaceIndex;NextHop=$_.NextHop;InterfaceAlias=$adapter.Name;"
            "RouteMetric=$_.RouteMetric;InterfaceMetric=$_.InterfaceMetric} }; "
            "$physical = $routes | Where-Object { $_.InterfaceAlias -notmatch 'WireGuard|WARP|OpenVPN|TAP|TUN|VPN' } | "
            "Select-Object -First 1; "
            "if (-not $physical) { $physical = $routes | Select-Object -First 1 }; "
            "$physical | Select-Object InterfaceIndex,NextHop | ConvertTo-Json -Compress"
        )
        result = run_command(["powershell.exe", "-NoProfile", "-Command", ps], timeout=15)
        if not result.ok or not result.stdout.strip():
            raise RuntimeError(result.text or "Не удалось определить основной шлюз.")
        data = json.loads(result.stdout)
        if isinstance(data, list):
            data = data[0]
        return DefaultGateway(int(data["InterfaceIndex"]), str(data["NextHop"]))

    def targets_to_dicts(self, targets: Iterable[RouteTarget]) -> list[dict[str, str]]:
        return [target.__dict__.copy() for target in targets]

    def dicts_to_targets(self, values: Iterable[dict[str, str]]) -> list[RouteTarget]:
        targets: list[RouteTarget] = []
        for value in values:
            cidr = value.get("cidr")
            source = value.get("source", cidr or "")
            if cidr:
                targets.append(RouteTarget(cidr, source))
        return targets

    @staticmethod
    def _cidr_to_route(cidr: str) -> tuple[str, str]:
        network = ipaddress.IPv4Network(cidr, strict=False)
        return str(network.network_address), str(network.netmask)

    @staticmethod
    def _unique_targets(targets: Iterable[RouteTarget]) -> list[RouteTarget]:
        seen: set[str] = set()
        unique: list[RouteTarget] = []
        for target in targets:
            if target.cidr in seen:
                continue
            seen.add(target.cidr)
            unique.append(target)
        return unique
