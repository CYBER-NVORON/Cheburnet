from __future__ import annotations

import re
import shutil
import time
from pathlib import Path
from typing import Any, Callable

from cheburnet.app.constants import SING_BOX_RELEASE_API
from cheburnet.app.core.archive import extract_archive
from cheburnet.app.core.downloader import download_file, get_json
from cheburnet.app.core.paths import app_root, tools_dir
from cheburnet.app.core.process import CommandResult, ProcessManager, run_command
from cheburnet.app.core.system import IS_WINDOWS, platform_key
from cheburnet.app.errors import ToolInstallError

Progress = Callable[[str], None]


class SingBoxService:
    def __init__(self, process_manager: ProcessManager | None = None) -> None:
        self.process_manager = process_manager or ProcessManager()

    def default_binary_path(self) -> Path:
        system, arch = platform_key()
        name = "sing-box.exe" if IS_WINDOWS else "sing-box"
        return tools_dir() / "sing-box" / f"{system}-{arch}" / name

    def detect_binary(self) -> Path | None:
        candidates = [self.default_binary_path()]
        exe = "sing-box.exe" if IS_WINDOWS else "sing-box"
        root = app_root()
        candidates.extend([root / exe, root / "tools" / exe, root / "tools" / "sing-box" / exe])
        for candidate in candidates:
            if candidate.exists():
                return candidate
        found = shutil.which(exe)
        return Path(found) if found else None

    def ensure_installed(self, progress: Progress | None = None) -> Path:
        detected = self.detect_binary()
        if detected:
            if self.version(detected):
                return detected
            if progress:
                progress("Найденный sing-box повреждён или не запускается, скачиваю заново")
            if detected == self.default_binary_path():
                try:
                    detected.unlink(missing_ok=True)
                except OSError:
                    pass
            else:
                return detected
        return self.download_latest(progress=progress)

    def latest_release(self) -> dict[str, Any]:
        return get_json(SING_BOX_RELEASE_API)

    def download_latest(self, progress: Progress | None = None) -> Path:
        release = self.latest_release()
        asset = self._pick_asset(release.get("assets", []))
        if not asset:
            raise ToolInstallError("В latest release sing-box не найден архив для текущей платформы.")
        target_dir = self.default_binary_path().parent
        target_dir.mkdir(parents=True, exist_ok=True)
        self.cleanup_old_downloads()
        archive_path = target_dir / str(asset["name"])
        download_file(str(asset["browser_download_url"]), archive_path, progress)
        extract_dir = target_dir / "_extract"
        if extract_dir.resolve().parent != target_dir.resolve():
            raise ToolInstallError("Некорректная временная папка распаковки sing-box.")
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_archive(archive_path, extract_dir)
        exe_name = "sing-box.exe" if IS_WINDOWS else "sing-box"
        unpacked = next(extract_dir.rglob(exe_name), None)
        if not unpacked:
            raise ToolInstallError(f"В архиве sing-box не найден {exe_name}.")
        target = self.default_binary_path()
        shutil.copy2(unpacked, target)
        if not IS_WINDOWS:
            target.chmod(0o755)
        archive_path.unlink(missing_ok=True)
        shutil.rmtree(extract_dir)
        self.cleanup_old_downloads()
        if progress:
            progress(f"sing-box установлен: {target}")
        return target

    def version(self, binary: Path | None = None) -> str:
        path = binary or self.detect_binary()
        if not path:
            return ""
        result = run_command([str(path), "version"], timeout=10)
        match = re.search(r"sing-box version\s+([^\s]+)", result.text, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r"\b(\d+\.\d+\.\d+[^\s]*)\b", result.text)
        return match.group(1) if match else ""

    def check_config(self, binary: Path, config_path: Path) -> CommandResult:
        return run_command([str(binary), "check", "-c", str(config_path)], timeout=30)

    def start(self, binary: Path, config_path: Path, on_output: Callable[[str], None] | None = None) -> None:
        self.process_manager.stop_current()
        managed = self.process_manager.start_process([str(binary), "run", "-c", str(config_path)], cwd=config_path.parent, on_output=on_output)
        deadline = time.time() + 2.5
        while time.time() < deadline:
            if managed.process.poll() is not None:
                raise RuntimeError("sing-box запустился и сразу завершился. Подробности в журнале.")
            time.sleep(0.1)

    def stop(self) -> None:
        self.process_manager.stop_current()
        if self.is_running():
            raise RuntimeError("sing-box не остановился штатно.")

    def is_running(self) -> bool:
        return bool(self.process_manager.current and self.process_manager.current.is_alive())

    def cleanup_old_downloads(self) -> None:
        target_dir = self.default_binary_path().parent
        if not target_dir.exists():
            return
        extract_dir = target_dir / "_extract"
        if extract_dir.exists():
            shutil.rmtree(extract_dir, ignore_errors=True)
        for pattern in ("*.zip", "*.tar.gz", "*.tgz"):
            for archive in target_dir.glob(pattern):
                archive.unlink(missing_ok=True)

    def _pick_asset(self, assets: Any) -> dict[str, Any] | None:
        if not isinstance(assets, list):
            return None
        system, arch = platform_key()
        suffix = ".zip" if system == "windows" else ".tar.gz"
        preferred = f"{system}-{arch}"
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name", "")).lower()
            if name.endswith(suffix) and preferred in name and "legacy" not in name and "browser_download_url" in asset:
                return asset
        return None
