from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .system import (
    CREATE_NO_WINDOW,
    IS_WINDOWS,
    SW_HIDE,
    CommandResult,
    is_admin,
    run_command,
    run_elevated,
    split_command_line,
)


LATEST_RELEASE_API = "https://api.github.com/repos/Flowseal/zapret-discord-youtube/releases/latest"
DEFAULT_TARGETS = {
    "Discord": "https://discord.com",
    "Discord Gateway": "https://gateway.discord.gg",
    "Discord CDN": "https://cdn.discordapp.com",
    "YouTube": "https://www.youtube.com",
    "YouTube Images": "https://i.ytimg.com",
    "GoogleVideo": "https://redirector.googlevideo.com",
    "Cloudflare DNS": "PING:1.1.1.1",
    "Google DNS": "PING:8.8.8.8",
}


Progress = Callable[[str], None]


@dataclass
class TargetCheck:
    name: str
    value: str
    ok: bool
    detail: str


@dataclass
class ConfigTestResult:
    config: str
    score: int
    checks: list[TargetCheck] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "config": self.config,
            "score": self.score,
            "checks": [check.__dict__ for check in self.checks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ConfigTestResult":
        checks = [
            TargetCheck(
                name=str(check.get("name", "")),
                value=str(check.get("value", "")),
                ok=bool(check.get("ok", False)),
                detail=str(check.get("detail", "")),
            )
            for check in data.get("checks", [])
            if isinstance(check, dict)
        ]
        return cls(str(data.get("config", "")), int(data.get("score", 0)), checks)


class ZapretController:
    def latest_release(self) -> dict[str, object]:
        request = urllib.request.Request(
            LATEST_RELEASE_API,
            headers={"User-Agent": "Cheburnet/0.1"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    def download_latest_zip(self, destination: str | Path, progress: Progress | None = None) -> Path:
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        release = self.latest_release()
        assets = release.get("assets", [])
        zip_asset = None
        if isinstance(assets, list):
            for asset in assets:
                if not isinstance(asset, dict):
                    continue
                name = str(asset.get("name", ""))
                if name.lower().endswith(".zip") and "browser_download_url" in asset:
                    zip_asset = asset
                    break
        if not zip_asset:
            raise RuntimeError("В latest release не найден zip-архив.")

        tag = str(release.get("tag_name") or release.get("name") or "latest")
        archive_path = destination / str(zip_asset["name"])
        if progress:
            progress(f"Скачиваю {archive_path.name} ({tag})...")
        urllib.request.urlretrieve(str(zip_asset["browser_download_url"]), archive_path)

        extract_dir = destination / f"zapret-discord-youtube-{tag}"
        if progress:
            progress(f"Распаковываю в {extract_dir}...")
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(extract_dir)
        return self.find_root(extract_dir)

    def find_root(self, path: str | Path) -> Path:
        root = Path(path)
        if (root / "service.bat").exists():
            return root
        for child in root.iterdir() if root.exists() else []:
            if child.is_dir() and (child / "service.bat").exists():
                return child
        return root

    def discover_configs(self, zapret_dir: str | Path) -> list[Path]:
        root = self.find_root(zapret_dir)
        if not root.exists():
            return []
        configs = [
            file
            for file in root.glob("*.bat")
            if file.name.lower().startswith("general") and file.name.lower() != "service.bat"
        ]
        return sorted(configs, key=self._natural_sort_key)

    def start_config(self, config_path: str | Path) -> subprocess.Popen[str] | None:
        config = Path(config_path)
        if not config.exists():
            raise FileNotFoundError(config)
        if IS_WINDOWS:
            winws, args = self.build_winws_command(config)
            self.prepare_runtime(config.parent)
            if not is_admin():
                run_elevated(str(winws), args, cwd=winws.parent, show=False)
                return None
            return self._popen_hidden([str(winws), *args], cwd=winws.parent)

        return subprocess.Popen(
            ["sh", str(config)],
            cwd=str(config.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            text=True,
        )

    def build_winws_command(self, config_path: str | Path) -> tuple[Path, list[str]]:
        config = Path(config_path)
        root = config.parent
        text = config.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
        text = re.sub(r"\^\s*\r?\n\s*", " ", text)
        text = text.replace("^", "")

        bin_dir = root / "bin"
        lists_dir = root / "lists"
        game_filter_tcp, game_filter_udp = self._game_filter_values(root)
        replacements = {
            "%~dp0": str(root) + "\\",
            "%BIN%": str(bin_dir) + "\\",
            "%LISTS%": str(lists_dir) + "\\",
            "%GameFilterTCP%": game_filter_tcp,
            "%GameFilterUDP%": game_filter_udp,
            "%GameFilter%": game_filter_tcp,
        }
        for key, value in replacements.items():
            text = re.sub(re.escape(key), lambda _match, replacement=value: replacement, text, flags=re.IGNORECASE)

        match = re.search(r'(?is)(?:"(?P<quoted>[^"]*winws\.exe)"|(?P<bare>\S*winws\.exe))(?P<args>.*)$', text)
        if not match:
            raise RuntimeError(f"Не удалось найти запуск winws.exe в {config.name}.")
        winws = Path(match.group("quoted") or match.group("bare"))
        if not winws.is_absolute():
            winws = root / winws
        if not winws.exists():
            raise RuntimeError(f"winws.exe не найден: {winws}")
        args_text = match.group("args").strip()
        args = split_command_line(args_text)
        return winws, args

    def prepare_runtime(self, root: str | Path) -> None:
        root = Path(root)
        lists = root / "lists"
        lists.mkdir(parents=True, exist_ok=True)
        for name in [
            "list-general.txt",
            "list-general-user.txt",
            "list-general-custom.txt",
            "list-exclude.txt",
            "list-exclude-user.txt",
            "ipset-all.txt",
            "ipset-all-user.txt",
            "ipset-all-custom.txt",
            "ipset-exclude.txt",
            "ipset-exclude-user.txt",
        ]:
            path = lists / name
            if not path.exists():
                path.write_text("# autogenerated by Cheburnet\n", encoding="utf-8")
        if IS_WINDOWS and is_admin():
            run_command(["netsh", "interface", "tcp", "set", "global", "timestamps=enabled"], timeout=10)

    def _popen_hidden(self, command: list[str], cwd: str | Path) -> subprocess.Popen[str]:
        flags = CREATE_NO_WINDOW if IS_WINDOWS else 0
        startupinfo = None
        if IS_WINDOWS:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = SW_HIDE
        return subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            text=True,
            creationflags=flags,
            startupinfo=startupinfo,
        )

    @staticmethod
    def _game_filter_values(root: Path) -> tuple[str, str]:
        enabled = root / "utils" / "game_filter.enabled"
        if not enabled.exists():
            return "12", "12"
        value = enabled.read_text(encoding="utf-8", errors="replace").strip().lower()
        if value == "all":
            return "1024-65535", "50000-65535"
        if value == "tcp":
            return "1024-65535", "12"
        if value == "udp":
            return "12", "50000-65535"
        return "12", "12"

    def stop_winws(self) -> CommandResult:
        if not IS_WINDOWS:
            return run_command(["pkill", "-f", "winws"], timeout=10)
        tasklist = run_command(["tasklist", "/FI", "IMAGENAME eq winws.exe"], timeout=10)
        if "winws.exe" not in tasklist.stdout.lower():
            return CommandResult(True, ["taskkill", "/IM", "winws.exe", "/F"], 0, "YouTube и Discord уже выключены.", "")
        result = run_command(["taskkill", "/IM", "winws.exe", "/F"], timeout=10)
        if result.ok:
            return CommandResult(True, result.command, result.code, "YouTube и Discord выключены.", "")
        return result

    def open_original_tests(self, zapret_dir: str | Path) -> subprocess.Popen[str]:
        root = self.find_root(zapret_dir)
        script = root / "utils" / "test zapret.ps1"
        if script.exists():
            return subprocess.Popen(
                ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                cwd=str(root),
                creationflags=0,
                text=True,
            )
        service = root / "service.bat"
        return subprocess.Popen(["cmd.exe", "/c", str(service)], cwd=str(root), text=True)

    def test_configs(
        self,
        zapret_dir: str | Path,
        configs: Iterable[Path] | None = None,
        progress: Progress | None = None,
        stop_event: threading.Event | None = None,
    ) -> list[ConfigTestResult]:
        root = self.find_root(zapret_dir)
        selected = list(configs) if configs is not None else self.discover_configs(root)
        if not selected:
            raise RuntimeError("Не найдены general*.bat в папке zapret.")

        results: list[ConfigTestResult] = []
        try:
            for index, config in enumerate(selected, start=1):
                if stop_event and stop_event.is_set():
                    break
                if progress:
                    progress(f"[{index}/{len(selected)}] Запускаю {config.name}")
                self.stop_winws()
                proc = self.start_config(config)
                time.sleep(5)

                checks: list[TargetCheck] = []
                score = 0
                for name, value in DEFAULT_TARGETS.items():
                    if stop_event and stop_event.is_set():
                        break
                    check = self._check_target(name, value)
                    checks.append(check)
                    if check.ok:
                        score += 1
                    if progress:
                        progress(f"  {name}: {check.detail}")

                if proc and proc.poll() is None:
                    proc.terminate()
                self.stop_winws()
                results.append(ConfigTestResult(config.name, score, checks))
                if progress:
                    progress(f"  Итог {config.name}: {score}/{len(DEFAULT_TARGETS)}")
        finally:
            self.stop_winws()
        return sorted(results, key=lambda item: item.score, reverse=True)

    def test_configs_single_admin_prompt(
        self,
        zapret_dir: str | Path,
        progress: Progress | None = None,
        stop_event: threading.Event | None = None,
    ) -> list[ConfigTestResult]:
        if not IS_WINDOWS or is_admin():
            return self.test_configs(zapret_dir, progress=progress, stop_event=stop_event)

        work_dir = Path(tempfile.mkdtemp(prefix="cheburnet-zapret-test-"))
        result_path = work_dir / "result.json"
        log_path = work_dir / "progress.log"
        project_root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
        args = self._worker_args(zapret_dir, result_path, log_path)
        if progress:
            progress("Один раз запрашиваю права администратора для всего теста zapret...")
        run_elevated(sys.executable, args, cwd=project_root, show=False)

        emitted = 0
        while not result_path.exists():
            if stop_event and stop_event.is_set():
                if progress:
                    progress("Elevated-тест уже запущен. Остановите winws вручную, если нужно прервать прямо сейчас.")
                break
            emitted = self._emit_log_delta(log_path, emitted, progress)
            time.sleep(0.5)
        emitted = self._emit_log_delta(log_path, emitted, progress)

        if not result_path.exists():
            raise RuntimeError("Elevated zapret-тест не вернул result.json.")
        data = json.loads(result_path.read_text(encoding="utf-8"))
        if not data.get("ok"):
            raise RuntimeError(str(data.get("error") or "Elevated zapret-тест завершился с ошибкой."))
        raw_results = data.get("results", [])
        if not isinstance(raw_results, list):
            raise RuntimeError("Elevated zapret-тест вернул некорректный формат результатов.")
        return [ConfigTestResult.from_dict(item) for item in raw_results if isinstance(item, dict)]

    def _worker_args(self, zapret_dir: str | Path, result_path: Path, log_path: Path) -> list[str]:
        base = [
            "--zapret-dir",
            str(self.find_root(zapret_dir)),
            "--result",
            str(result_path),
            "--log",
            str(log_path),
        ]
        if getattr(sys, "frozen", False):
            return ["--zapret-worker", *base]
        return ["-m", "cheburnet.zapret_worker", *base]

    @staticmethod
    def _emit_log_delta(log_path: Path, emitted: int, progress: Progress | None) -> int:
        if not progress or not log_path.exists():
            return emitted
        text = log_path.read_text(encoding="utf-8", errors="replace")
        chunk = text[emitted:]
        for line in chunk.splitlines():
            progress(line)
        return len(text)

    def _check_target(self, name: str, value: str) -> TargetCheck:
        if value.startswith("PING:"):
            host = value.split(":", 1)[1]
            command = ["ping", "-n", "3", host] if IS_WINDOWS else ["ping", "-c", "3", host]
            result = run_command(command, timeout=8)
            ok = result.ok and ("TTL=" in result.stdout.upper() or "ttl=" in result.stdout)
            detail = "ping OK" if ok else "ping timeout"
            return TargetCheck(name, value, ok, detail)

        curl_checks = [
            ["curl.exe", "-I", "-s", "-m", "5", "-o", "NUL", "-w", "%{http_code}", "--http1.1", value],
            ["curl.exe", "-I", "-s", "-m", "5", "-o", "NUL", "-w", "%{http_code}", "--tlsv1.2", "--tls-max", "1.2", value],
        ]
        details: list[str] = []
        ok_count = 0
        for command in curl_checks:
            result = run_command(command, timeout=8)
            code = (result.stdout or "").strip()[-3:]
            ok = result.ok and code.isdigit() and code != "000"
            ok_count += int(ok)
            details.append(code if code else "ERR")
        return TargetCheck(name, value, ok_count > 0, "/".join(details))

    @staticmethod
    def _natural_sort_key(path: Path) -> list[object]:
        return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", path.name)]
