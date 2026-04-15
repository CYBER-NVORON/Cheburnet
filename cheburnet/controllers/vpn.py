from __future__ import annotations

import html
import os
import re
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from cheburnet.config import app_data_dir

from .system import CREATE_NO_WINDOW, IS_WINDOWS, CommandResult, find_executable, run_command, run_elevated


WIREGUARD_CANDIDATES = [
    r"C:\Program Files\WireGuard\wireguard.exe",
    r"C:\Program Files (x86)\WireGuard\wireguard.exe",
]
OPENVPN_CANDIDATES = [
    r"C:\Program Files\OpenVPN\bin\openvpn.exe",
]
WARP_CANDIDATES = [
    r"C:\Program Files\Cloudflare\Cloudflare WARP\warp-cli.exe",
    r"C:\Program Files (x86)\Cloudflare\Cloudflare WARP\warp-cli.exe",
]
WIREGUARD_INSTALLER_URL = "https://download.wireguard.com/windows-client/wireguard-installer.exe"
OPENVPN_COMMUNITY_URL = "https://openvpn.net/community/"
WARP_INSTALLER_URL = "https://downloads.cloudflareclient.com/v1/download/windows/ga"
Progress = Callable[[str], None]


@dataclass
class VpnOperation:
    ok: bool
    message: str


class VpnController:
    def __init__(self) -> None:
        self._openvpn_process: subprocess.Popen[str] | None = None

    def detect_tools(self) -> dict[str, str | None]:
        return {
            "wireguard": find_executable("wireguard.exe", WIREGUARD_CANDIDATES),
            "openvpn": find_executable("openvpn.exe", OPENVPN_CANDIDATES),
            "warp": find_executable("warp-cli.exe", WARP_CANDIDATES),
        }

    def make_profile(self, protocol: str, config_path: str = "", name: str = "") -> dict[str, Any]:
        protocol = protocol.lower()
        if not name:
            if protocol == "warp":
                name = "Cloudflare WARP"
            elif config_path:
                name = Path(config_path).stem
            else:
                name = protocol.upper()
        return {"id": self._profile_id(name), "name": name, "protocol": protocol, "config_path": config_path}

    def connect(self, profile: dict[str, Any]) -> VpnOperation:
        protocol = str(profile.get("protocol", "")).lower()
        if protocol == "wireguard":
            return self._connect_wireguard(profile)
        if protocol == "openvpn":
            return self._connect_openvpn(profile)
        if protocol == "warp":
            return self._warp(["connect"])
        return VpnOperation(False, f"Неизвестный VPN-протокол: {protocol}")

    def disconnect(self, profile: dict[str, Any]) -> VpnOperation:
        protocol = str(profile.get("protocol", "")).lower()
        if protocol == "wireguard":
            return self._disconnect_wireguard(profile)
        if protocol == "openvpn":
            return self._disconnect_openvpn()
        if protocol == "warp":
            return self._warp(["disconnect"])
        return VpnOperation(False, f"Неизвестный VPN-протокол: {protocol}")

    def status(self) -> str:
        tools = self.detect_tools()
        parts = []
        for name, path in tools.items():
            parts.append(f"{name}: {'найден' if path else 'не найден'}")
        if tools["warp"]:
            result = run_command([tools["warp"], "status"], timeout=10)
            if result.text:
                parts.append(result.text.strip())
        return "\n".join(parts)

    def download_and_run_installer(self, component: str, progress: Progress | None = None) -> VpnOperation:
        component = component.lower()
        if component == "wireguard":
            path = self._download_file(WIREGUARD_INSTALLER_URL, "wireguard-installer.exe", progress)
            self._run_installer(path)
            return VpnOperation(True, f"WireGuard installer запущен: {path}")
        if component == "openvpn":
            url = self._latest_openvpn_amd64_url()
            name = Path(urllib.parse.urlparse(url).path).name or "openvpn-amd64.msi"
            path = self._download_file(url, name, progress)
            self._run_installer(path)
            return VpnOperation(True, f"OpenVPN installer запущен: {path}")
        if component == "warp":
            path = self._download_file(WARP_INSTALLER_URL, "Cloudflare_WARP_Windows.msi", progress)
            self._run_installer(path)
            return VpnOperation(True, f"Cloudflare WARP installer запущен: {path}")
        return VpnOperation(False, f"Неизвестный компонент: {component}")

    def _connect_wireguard(self, profile: dict[str, Any]) -> VpnOperation:
        tool = self.detect_tools()["wireguard"]
        if not tool:
            return VpnOperation(False, "WireGuard не найден. Установите WireGuard for Windows.")
        config = Path(str(profile.get("config_path", "")))
        if not config.exists():
            return VpnOperation(False, f"WireGuard-конфиг не найден: {config}")
        result = run_command([tool, "/installtunnelservice", str(config)], timeout=30, no_window=False)
        if result.ok:
            return VpnOperation(True, f"WireGuard tunnel service установлен: {config.stem}")
        if "already exists" in result.text.lower():
            return VpnOperation(True, f"WireGuard tunnel service уже установлен: {config.stem}")
        return VpnOperation(False, result.text or "WireGuard не смог установить tunnel service.")

    def _disconnect_wireguard(self, profile: dict[str, Any]) -> VpnOperation:
        tool = self.detect_tools()["wireguard"]
        if not tool:
            return VpnOperation(False, "WireGuard не найден.")
        tunnel = Path(str(profile.get("config_path", ""))).stem or str(profile.get("name", ""))
        if not tunnel:
            return VpnOperation(False, "Не удалось определить имя WireGuard tunnel.")
        result = run_command([tool, "/uninstalltunnelservice", tunnel], timeout=30, no_window=False)
        if result.ok:
            return VpnOperation(True, f"WireGuard tunnel service удалён: {tunnel}")
        return VpnOperation(False, result.text or "WireGuard не смог удалить tunnel service.")

    def _connect_openvpn(self, profile: dict[str, Any]) -> VpnOperation:
        tool = self.detect_tools()["openvpn"]
        if not tool:
            return VpnOperation(False, "OpenVPN не найден. Установите OpenVPN Community.")
        config = Path(str(profile.get("config_path", "")))
        if not config.exists():
            return VpnOperation(False, f"OpenVPN-конфиг не найден: {config}")
        if self._openvpn_process and self._openvpn_process.poll() is None:
            return VpnOperation(True, "OpenVPN уже запущен этим приложением.")
        flags = CREATE_NO_WINDOW if IS_WINDOWS else 0
        self._openvpn_process = subprocess.Popen(
            [tool, "--config", str(config)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            text=True,
            creationflags=flags,
        )
        return VpnOperation(True, f"OpenVPN запущен: {config.name}")

    def _disconnect_openvpn(self) -> VpnOperation:
        if not self._openvpn_process or self._openvpn_process.poll() is not None:
            return VpnOperation(True, "OpenVPN-процесс этого приложения не запущен.")
        self._openvpn_process.terminate()
        try:
            self._openvpn_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._openvpn_process.kill()
        return VpnOperation(True, "OpenVPN остановлен.")

    def _warp(self, args: list[str]) -> VpnOperation:
        tool = self.detect_tools()["warp"]
        if not tool:
            return VpnOperation(False, "Cloudflare WARP CLI не найден. Установите Cloudflare WARP.")
        result = run_command([tool, *args], timeout=30, no_window=False)
        return VpnOperation(result.ok, result.text or ("Команда WARP выполнена." if result.ok else "WARP вернул ошибку."))

    def _download_file(self, url: str, fallback_name: str, progress: Progress | None = None) -> Path:
        directory = app_data_dir() / "installers"
        directory.mkdir(parents=True, exist_ok=True)
        if progress:
            progress(f"Скачиваю: {url}")
        request = urllib.request.Request(url, headers={"User-Agent": "Cheburnet/0.1"})
        with urllib.request.urlopen(request, timeout=90) as response:
            filename = self._filename_from_response(response.headers.get("Content-Disposition", "")) or fallback_name
            target = directory / filename
            data = response.read()
        target.write_bytes(data)
        if progress:
            progress(f"Сохранено: {target}")
        return target

    def _latest_openvpn_amd64_url(self) -> str:
        request = urllib.request.Request(OPENVPN_COMMUNITY_URL, headers={"User-Agent": "Cheburnet/0.1"})
        with urllib.request.urlopen(request, timeout=30) as response:
            page = response.read().decode("utf-8", errors="replace")
        page = html.unescape(page)
        match = re.search(r'https://swupdate\.openvpn\.org/[^\s"\']+amd64\.msi', page, re.IGNORECASE)
        if not match:
            raise RuntimeError("Не удалось найти OpenVPN amd64 MSI на официальной странице.")
        return match.group(0)

    def _run_installer(self, path: Path) -> None:
        if not IS_WINDOWS:
            raise RuntimeError("Автоустановка компонентов реализована только для Windows.")
        suffix = path.suffix.lower()
        if suffix == ".msi":
            run_elevated("msiexec.exe", ["/i", str(path)])
            return
        run_elevated(str(path), [])

    @staticmethod
    def _filename_from_response(content_disposition: str) -> str:
        match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', content_disposition, re.IGNORECASE)
        if not match:
            return ""
        return Path(urllib.parse.unquote(match.group(1))).name

    @staticmethod
    def _profile_id(name: str) -> str:
        text = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip()).strip("-").lower()
        return text or "vpn-profile"
