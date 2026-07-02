from __future__ import annotations

import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from cheburnet.app.core.paths import generated_dir
from cheburnet.app.core.process import CREATE_NO_WINDOW, IS_WINDOWS, _hidden_startupinfo, run_command
from cheburnet.app.models.health import HealthCheckResult, HealthStatus
from cheburnet.app.models.profile import Profile, RoutingMode
from cheburnet.app.models.server import ServerCheck
from cheburnet.app.services.singbox_config_builder import SingBoxConfigBuilder


class HealthcheckService:
    def tcp_check(self, profile: Profile, timeout: float = 3.0) -> ServerCheck:
        if not profile.host or not profile.port:
            return ServerCheck(profile.id, "syntax_error", None, "Нет host/port")
        started = time.perf_counter()
        try:
            with socket.create_connection((profile.host, profile.port), timeout=timeout):
                latency = int((time.perf_counter() - started) * 1000)
        except OSError as exc:
            return ServerCheck(profile.id, "tcp_failed", None, str(exc))
        return ServerCheck(profile.id, "online", latency, "TCP OK")

    def http_check(self, target: str, timeout: float = 8.0) -> HealthCheckResult:
        urls = {
            "youtube": ["https://www.youtube.com/generate_204", "https://www.youtube.com/"],
            "discord": ["https://discord.com/api/v10/gateway", "https://discord.com/"],
        }.get(target, [target])
        started = time.perf_counter()
        last_error = ""
        for url in urls:
            try:
                request = urllib.request.Request(url, method="GET", headers={"User-Agent": "CheburNet/0.2"})
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    code = int(response.status)
                    latency = int((time.perf_counter() - started) * 1000)
                    if 200 <= code < 500:
                        return HealthCheckResult(target, HealthStatus.OK, f"HTTP {code}", latency)
                    last_error = f"HTTP {code}"
            except urllib.error.HTTPError as exc:
                code = int(exc.code)
                latency = int((time.perf_counter() - started) * 1000)
                if 200 <= code < 500:
                    return HealthCheckResult(target, HealthStatus.OK, f"HTTP {code}", latency)
                last_error = f"HTTP {code}"
            except TimeoutError:
                return HealthCheckResult(target, HealthStatus.TIMEOUT, "Таймаут проверки")
            except urllib.error.URLError as exc:
                if isinstance(exc.reason, TimeoutError):
                    return HealthCheckResult(target, HealthStatus.TIMEOUT, "Таймаут проверки")
                last_error = str(exc.reason)
            except OSError as exc:
                last_error = str(exc)
        return HealthCheckResult(target, HealthStatus.FAILED, last_error or "Проверка не прошла")

    def internet_check(self, timeout: float = 10.0) -> HealthCheckResult:
        return self.http_check("https://www.gstatic.com/generate_204", timeout=timeout)

    def check_youtube_discord(self) -> dict[str, HealthCheckResult]:
        return {
            "youtube": self.http_check("youtube"),
            "discord": self.http_check("discord"),
        }

    def check_vpn_ready(self, profile: Profile, attempts: int = 3, delay: float = 2.0) -> ServerCheck:
        last = HealthCheckResult("internet", HealthStatus.FAILED, "Проверка не запускалась")
        for attempt in range(max(attempts, 1)):
            result = self.internet_check()
            if result.status == HealthStatus.OK:
                return ServerCheck(profile.id, "online", result.latency_ms, result.detail)
            last = result
            if attempt < attempts - 1:
                time.sleep(delay)
        return ServerCheck(profile.id, last.status.value, last.latency_ms, last.detail)

    def check_profile_with_singbox(
        self,
        profile: Profile,
        singbox_binary: Path,
        builder: SingBoxConfigBuilder,
        settings: dict,
        version: str,
        progress: Callable[[str], None] | None = None,
    ) -> Profile:
        if profile.protocol != "wireguard":
            tcp = self.tcp_check(profile)
            profile.latency_ms = tcp.latency_ms
            if tcp.status != "online":
                profile.status = "tcp_failed" if tcp.status == "tcp_failed" else "syntax_error"
                profile.meta["last_check_detail"] = tcp.detail
                return profile

        try:
            if profile.protocol == "wireguard":
                config_path = builder.build(profile, settings, RoutingMode.FULL_VPN, version, generated_dir() / f"check-{profile.id}.json")
            else:
                port = self._free_port()
                config_path = builder.build_probe_config(profile, port, generated_dir() / f"check-{profile.id}.json")
        except Exception as exc:
            profile.status = "syntax_error"
            profile.meta["last_check_detail"] = str(exc)
            return profile

        check = run_command([str(singbox_binary), "check", "-c", str(config_path)], timeout=20)
        if not check.ok:
            profile.status = "syntax_error"
            profile.meta["last_check_detail"] = check.text or "sing-box check failed"
            return profile

        if profile.protocol == "wireguard":
            profile.status = "online"
            profile.meta["last_check_detail"] = "sing-box check OK; активный WireGuard probe пропущен"
            return profile

        active = self._short_proxy_probe(singbox_binary, config_path, profile.id, progress)
        profile.status = active[0]
        profile.meta["last_check_detail"] = active[1]
        return profile

    def _short_proxy_probe(
        self,
        singbox_binary: Path,
        config_path: Path,
        profile_id: str,
        progress: Callable[[str], None] | None,
    ) -> tuple[str, str]:
        port = self._extract_probe_port(config_path)
        flags = CREATE_NO_WINDOW if IS_WINDOWS else 0
        process = subprocess.Popen(
            [str(singbox_binary), "run", "-c", str(config_path)],
            cwd=str(config_path.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
            startupinfo=_hidden_startupinfo(),
        )
        try:
            time.sleep(1.5)
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout else ""
                return "failed", output.strip() or "sing-box завершился сразу"
            curl = shutil.which("curl.exe" if IS_WINDOWS else "curl")
            if not curl:
                return "online", "sing-box check OK; curl не найден, активный HTTP probe пропущен"
            result = run_command(
                [
                    curl,
                    "-L",
                    "-sS",
                    "-k",
                    "--connect-timeout",
                    "5",
                    "-m",
                    "10",
                    "-o",
                    "NUL" if IS_WINDOWS else "/dev/null",
                    "-w",
                    "%{http_code}",
                    "--proxy",
                    f"socks5h://127.0.0.1:{port}",
                    "https://www.gstatic.com/generate_204",
                ],
                timeout=13,
            )
            code = result.stdout.strip()[-3:]
            if result.ok and code.isdigit() and code != "000":
                return "online", f"HTTP probe OK {code}"
            return "unstable", result.text or f"HTTP probe failed {code}"
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            if progress:
                progress(f"Проверка профиля {profile_id}: завершена")

    @staticmethod
    def _extract_probe_port(config_path: Path) -> int:
        import json

        data = json.loads(config_path.read_text(encoding="utf-8"))
        return int(data["inbounds"][0]["listen_port"])

    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])
