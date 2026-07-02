from __future__ import annotations

import ctypes
import os
import re
import shlex
import shutil
import time
from pathlib import Path
from typing import Any, Callable

from cheburnet.app.constants import ZAPRET_HOSTS_URL, ZAPRET_IPSET_URL, ZAPRET_RELEASE_API, ZAPRET_VERSION_URL
from cheburnet.app.core.archive import extract_archive
from cheburnet.app.core.downloader import download_file, get_json, get_text
from cheburnet.app.core.paths import tools_dir
from cheburnet.app.core.process import ProcessManager, run_command
from cheburnet.app.core.system import IS_WINDOWS
from cheburnet.app.errors import ToolInstallError

Progress = Callable[[str], None]


class ZapretService:
    def __init__(self, install_dir: str | Path | None = None, process_manager: ProcessManager | None = None) -> None:
        self.process_manager = process_manager or ProcessManager()
        self._install_dir = Path(install_dir) if install_dir else None

    def install_dir(self) -> Path:
        path = self._install_dir or tools_dir() / "zapret"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def set_install_dir(self, path: str | Path) -> Path:
        root = self.find_root(path)
        if not root or not root.exists():
            raise RuntimeError(f"Папка Zapret не найдена: {path}")
        if not self.available_scripts(root):
            raise RuntimeError("В выбранной папке не найдены подходящие .bat-сценарии Zapret.")
        self._install_dir = root
        return root

    def latest_release(self) -> dict[str, Any]:
        return get_json(ZAPRET_RELEASE_API, timeout=30)

    def local_version(self, root: str | Path | None = None) -> str:
        base = Path(root) if root else self.find_root()
        if not base:
            return ""
        service_bat = base / "service.bat"
        if not service_bat.exists():
            return ""
        text = service_bat.read_text(encoding="utf-8", errors="replace")
        match = re.search(r'set\s+"LOCAL_VERSION=([^"]+)"', text, flags=re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def check_for_updates(self) -> str:
        local = self.local_version() or "неизвестно"
        latest = get_text(ZAPRET_VERSION_URL, timeout=10).strip()
        if not latest:
            return f"Локальная версия: {local}. Не удалось получить актуальную версию."
        if local == latest:
            return f"Zapret актуален: {local}"
        return f"Доступна новая версия Zapret: {latest}. Установлена: {local}"

    def is_installed(self) -> bool:
        return bool(self.find_root() and self.available_scripts())

    def update_ipset_list(self) -> Path:
        root = self.find_root()
        if not root:
            raise RuntimeError("zapret не установлен.")
        list_file = root / "lists" / "ipset-all.txt"
        download_file(ZAPRET_IPSET_URL, list_file)
        return list_file

    def update_hosts_file(self) -> str:
        if not IS_WINDOWS:
            raise RuntimeError("Обновление hosts реализовано только для Windows.")
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        hosts_file = Path(system_root) / "System32" / "drivers" / "etc" / "hosts"
        remote_text = get_text(ZAPRET_HOSTS_URL, timeout=20).strip()
        if not remote_text:
            raise RuntimeError("Не удалось скачать hosts из репозитория Flowseal.")
        hosts_file.parent.mkdir(parents=True, exist_ok=True)
        current = hosts_file.read_text(encoding="utf-8", errors="replace") if hosts_file.exists() else ""
        first_line = next((line for line in remote_text.splitlines() if line.strip()), "")
        last_line = next((line for line in reversed(remote_text.splitlines()) if line.strip()), "")
        if first_line and last_line and first_line in current and last_line in current:
            return "hosts уже актуален."
        backup = hosts_file.with_name("hosts.cheburnet.bak")
        if hosts_file.exists() and not backup.exists():
            shutil.copy2(hosts_file, backup)
        begin = "# CheburNet Flowseal zapret hosts BEGIN"
        end = "# CheburNet Flowseal zapret hosts END"
        block = f"{begin}\n{remote_text}\n{end}"
        pattern = re.compile(rf"{re.escape(begin)}.*?{re.escape(end)}", re.DOTALL)
        if pattern.search(current):
            updated = pattern.sub(block, current)
        else:
            updated = current.rstrip() + "\n\n" + block + "\n"
        hosts_file.write_text(updated, encoding="utf-8")
        return f"hosts обновлён. Резервная копия: {backup}"

    def run_diagnostics(self) -> str:
        if not IS_WINDOWS:
            return "Диагностика Flowseal доступна только на Windows."
        root = self.find_root()
        lines: list[str] = []
        lines.append(self._diagnostic_service_running("BFE", "Base Filtering Engine"))
        proxy = run_command(
            ["reg", "query", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings", "/v", "ProxyEnable"],
            timeout=5,
        )
        lines.append("Proxy: включён" if "0x1" in proxy.stdout else "Proxy: OK")
        tcp = run_command(["netsh", "interface", "tcp", "show", "global"], timeout=8)
        if "enabled" in tcp.stdout.lower() and "timestamps" in tcp.stdout.lower():
            lines.append("TCP timestamps: OK")
        else:
            enable = run_command(["netsh", "interface", "tcp", "set", "global", "timestamps=enabled"], timeout=10)
            lines.append("TCP timestamps: включены" if enable.ok else "TCP timestamps: не удалось включить")
        for process, label in (("AdguardSvc.exe", "Adguard"),):
            lines.append(f"{label}: найден, может мешать" if self._process_running(process) else f"{label}: OK")
        for query, label in (
            ("Killer", "Killer services"),
            ("Intel", "Intel Connectivity"),
            ("TracSrvWrapper", "Check Point"),
            ("SmartByte", "SmartByte"),
        ):
            lines.append(f"{label}: найден, может мешать" if self._service_query_contains(query) else f"{label}: OK")
        if root and not any((root / "bin").glob("*.sys")):
            lines.append("WinDivert64.sys: не найден")
        else:
            lines.append("WinDivert64.sys: OK")
        vpn = self._service_query_contains("VPN")
        lines.append("VPN services: найдены, отключите на время Zapret" if vpn else "VPN services: OK")
        hosts_file = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
        hosts_text = hosts_file.read_text(encoding="utf-8", errors="replace").lower() if hosts_file.exists() else ""
        lines.append("hosts: есть записи YouTube, проверьте их" if "youtube.com" in hosts_text or "youtu.be" in hosts_text else "hosts: OK")
        conflicts = [name for name in ("GoodbyeDPI", "discordfix_zapret", "winws1", "winws2") if self._service_state(name) != "не установлен"]
        lines.append(f"Конфликтующие службы: {', '.join(conflicts)}" if conflicts else "Конфликтующие службы: не найдены")
        return "\n".join(lines)

    def options(self) -> dict[str, object]:
        root = self.find_root()
        if not root:
            return {"game_filter": "off", "ipset_filter": False, "update_check": False}
        return {
            "game_filter": self.game_filter(root),
            "ipset_filter": self.ipset_status(root) == "loaded",
            "update_check": (root / "utils" / "check_updates.enabled").exists(),
        }

    def set_options(self, values: dict[str, object]) -> None:
        root = self.find_root()
        if not root:
            raise RuntimeError("zapret не установлен.")
        if "game_filter" in values:
            self.set_game_filter(str(values["game_filter"]), root)
        if "ipset_filter" in values:
            self.set_ipset_filter(bool(values["ipset_filter"]), root)
        if "update_check" in values:
            self.set_update_check(bool(values["update_check"]), root)

    def game_filter(self, root: str | Path | None = None) -> str:
        base = Path(root) if root else self.find_root()
        if not base:
            return "off"
        enabled = base / "utils" / "game_filter.enabled"
        if not enabled.exists():
            return "off"
        value = enabled.read_text(encoding="utf-8", errors="replace").strip().lower()
        return value if value in {"tcp", "udp", "all"} else "off"

    def set_game_filter(self, mode: str, root: str | Path | None = None) -> None:
        base = Path(root) if root else self.find_root()
        if not base:
            raise RuntimeError("zapret не установлен.")
        utils = base / "utils"
        utils.mkdir(parents=True, exist_ok=True)
        enabled = utils / "game_filter.enabled"
        value = mode if mode in {"tcp", "udp", "all"} else "off"
        if value == "off":
            enabled.unlink(missing_ok=True)
        else:
            enabled.write_text(value, encoding="utf-8")

    def ipset_status(self, root: str | Path | None = None) -> str:
        base = Path(root) if root else self.find_root()
        if not base:
            return "none"
        list_file = base / "lists" / "ipset-all.txt"
        if not list_file.exists():
            return "none"
        text = list_file.read_text(encoding="utf-8", errors="replace")
        lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
        if not lines:
            return "any"
        return "none" if any("203.0.113.113/32" in line for line in lines) else "loaded"

    def set_ipset_filter(self, enabled: bool, root: str | Path | None = None) -> None:
        base = Path(root) if root else self.find_root()
        if not base:
            raise RuntimeError("zapret не установлен.")
        lists = base / "lists"
        lists.mkdir(parents=True, exist_ok=True)
        list_file = lists / "ipset-all.txt"
        backup = lists / "ipset-all.cheburnet-backup.txt"
        if enabled:
            if backup.exists():
                backup.replace(list_file)
            elif not list_file.exists():
                list_file.write_text("", encoding="utf-8")
            return
        if list_file.exists() and self.ipset_status(base) == "loaded":
            shutil.copy2(list_file, backup)
        list_file.write_text("203.0.113.113/32\n", encoding="utf-8")

    def set_update_check(self, enabled: bool, root: str | Path | None = None) -> None:
        base = Path(root) if root else self.find_root()
        if not base:
            raise RuntimeError("zapret не установлен.")
        utils = base / "utils"
        utils.mkdir(parents=True, exist_ok=True)
        flag = utils / "check_updates.enabled"
        if enabled:
            flag.write_text("", encoding="utf-8")
        else:
            flag.unlink(missing_ok=True)

    def find_root(self, base: str | Path | None = None) -> Path | None:
        root = Path(base) if base else self.install_dir()
        if not root.exists():
            return None
        if (root / "service.bat").exists() or (root / "bin").exists():
            return root
        for child in root.iterdir():
            if child.is_dir() and ((child / "service.bat").exists() or (child / "bin").exists()):
                return child
        return root

    def download_latest(self, progress: Progress | None = None) -> Path:
        release = self.latest_release()
        assets = release.get("assets", [])
        zip_asset = None
        if isinstance(assets, list):
            for asset in assets:
                if isinstance(asset, dict) and str(asset.get("name", "")).lower().endswith(".zip"):
                    zip_asset = asset
                    break
        if not zip_asset:
            raise ToolInstallError("В latest release zapret не найден zip-архив.")
        tag = str(release.get("tag_name") or release.get("name") or "latest")
        destination = self._download_destination()
        archive_path = destination / str(zip_asset["name"])
        download_file(str(zip_asset["browser_download_url"]), archive_path, progress)
        extract_dir = destination / f"zapret-discord-youtube-{tag}"
        if extract_dir.resolve().parent != destination.resolve():
            raise ToolInstallError("Некорректная временная папка zapret.")
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_archive(archive_path, extract_dir)
        archive_path.unlink(missing_ok=True)
        root = self.find_root(extract_dir)
        if not root:
            raise ToolInstallError("Архив zapret распакован, но корень проекта не найден.")
        self._install_dir = root
        if progress:
            progress(f"zapret установлен: {root}")
        return root

    def _download_destination(self) -> Path:
        configured = self._install_dir or tools_dir() / "zapret"
        configured.mkdir(parents=True, exist_ok=True)
        current_root = self.find_root(configured)
        if current_root and current_root.exists() and ((current_root / "service.bat").exists() or (current_root / "bin").exists()):
            if current_root.resolve() == configured.resolve():
                return current_root.parent
            return configured
        return configured

    def available_scripts(self, base: str | Path | None = None) -> list[Path]:
        root = self.find_root(base)
        if not root or not root.exists():
            return []
        scripts: list[Path] = []
        for path in root.rglob("*.bat"):
            try:
                relative = path.relative_to(root)
            except ValueError:
                continue
            if len(relative.parts) > 2:
                continue
            name = path.stem.lower()
            if not name.startswith("general"):
                continue
            scripts.append(path)
        return sorted(scripts, key=lambda item: item.name.lower())

    def start_script(self, script: Path, on_output: Callable[[str], None] | None = None) -> None:
        root = self.find_root()
        if not root:
            raise RuntimeError("zapret не установлен.")
        script_resolved = script.resolve()
        root_resolved = root.resolve()
        if script_resolved != root_resolved and root_resolved not in script_resolved.parents:
            raise RuntimeError("Запуск bat вне папки tools/zapret запрещён.")
        if not script.exists() or script.suffix.lower() != ".bat":
            raise RuntimeError(f"Сценарий zapret не найден: {script}")
        if IS_WINDOWS:
            winws, args = self.build_winws_command(script)
            self.prepare_runtime(root)
            managed = self.process_manager.start_process(
                [str(winws), *args],
                cwd=winws.parent,
                on_output=on_output,
            )
        else:
            managed = self.process_manager.start_process(["sh", str(script)], cwd=script.parent, on_output=on_output)
        deadline = time.time() + 3.0
        while time.time() < deadline:
            if self.is_running():
                return
            time.sleep(0.15)
        if not self.is_running():
            raise RuntimeError("Zapret запустился и сразу завершился. Подробности в журнале.")

    def stop(self) -> None:
        self.process_manager.stop_current()
        if IS_WINDOWS:
            run_command(["taskkill", "/IM", "winws.exe", "/T", "/F"], timeout=8)
        else:
            run_command(["pkill", "-f", "winws"], timeout=8)
        if self.is_running():
            raise RuntimeError("Zapret не остановился штатно.")

    def is_running(self) -> bool:
        if IS_WINDOWS:
            result = run_command(["tasklist", "/FI", "IMAGENAME eq winws.exe"], timeout=5)
            return result.ok and "winws.exe" in result.stdout.lower()
        if self.process_manager.current and self.process_manager.current.is_alive():
            return True
        result = run_command(["pgrep", "-f", "winws"], timeout=5)
        return result.ok

    @staticmethod
    def _service_state(name: str) -> str:
        result = run_command(["sc", "query", name], timeout=5)
        if not result.ok:
            return "не установлен"
        text = result.stdout.upper()
        if "RUNNING" in text:
            return "запущен"
        if "STOP_PENDING" in text:
            return "останавливается"
        if "START_PENDING" in text:
            return "запускается"
        if "STOPPED" in text:
            return "остановлен"
        return "найден"

    @classmethod
    def _diagnostic_service_running(cls, service_name: str, label: str) -> str:
        state = cls._service_state(service_name)
        return f"{label}: OK" if state == "запущен" else f"{label}: {state}"

    @staticmethod
    def _process_running(name: str) -> bool:
        result = run_command(["tasklist", "/FI", f"IMAGENAME eq {name}"], timeout=5)
        return result.ok and name.lower() in result.stdout.lower()

    @staticmethod
    def _service_query_contains(text: str) -> bool:
        result = run_command(["sc", "query"], timeout=10)
        return result.ok and text.lower() in result.stdout.lower()

    @staticmethod
    def build_winws_command(script: Path) -> tuple[Path, list[str]]:
        root = script.parent
        text = script.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
        text = re.sub(r"\^\s*\r?\n\s*", " ", text)
        text = text.replace("^", "")

        bin_dir = root / "bin"
        lists_dir = root / "lists"
        game_filter_tcp, game_filter_udp = ZapretService._game_filter_values(root)
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
            raise RuntimeError(f"Не удалось найти запуск winws.exe в {script.name}.")
        winws = Path(match.group("quoted") or match.group("bare"))
        if not winws.is_absolute():
            winws = root / winws
        if not winws.exists():
            raise RuntimeError(f"winws.exe не найден: {winws}")
        args = ZapretService._split_command_line(match.group("args").strip())
        return winws, args

    @staticmethod
    def prepare_runtime(root: str | Path) -> None:
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
                path.write_text("# autogenerated by CheburNet\n", encoding="utf-8")
        if IS_WINDOWS:
            run_command(["netsh", "interface", "tcp", "set", "global", "timestamps=enabled"], timeout=10)

    @staticmethod
    def _split_command_line(command_line: str) -> list[str]:
        if not command_line:
            return []
        if not IS_WINDOWS:
            return shlex.split(command_line)
        argc = ctypes.c_int()
        command_line_to_argv = ctypes.windll.shell32.CommandLineToArgvW
        command_line_to_argv.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
        command_line_to_argv.restype = ctypes.POINTER(ctypes.c_wchar_p)
        argv = command_line_to_argv(command_line, ctypes.byref(argc))
        if not argv:
            raise RuntimeError("CommandLineToArgvW failed.")
        try:
            return [argv[index] for index in range(argc.value)]
        finally:
            ctypes.windll.kernel32.LocalFree(argv)

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

    @staticmethod
    def _hidden_script(script: Path) -> Path:
        text = script.read_text(encoding="utf-8", errors="replace")
        patched = re.sub(
            r'start\s+"zapret:\s*%~n0"\s+/min\s+',
            'start "" /b ',
            text,
            flags=re.IGNORECASE,
        )
        target = script.with_name(f"cheburnet-hidden-{script.stem}.bat")
        target.write_text(patched, encoding="utf-8")
        return target
