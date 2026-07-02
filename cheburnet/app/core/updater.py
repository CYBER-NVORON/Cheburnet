from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from cheburnet.app.constants import APP_NAME, APP_VERSION, CHEBURNET_RELEASE_API
from cheburnet.app.core.archive import extract_archive
from cheburnet.app.core.downloader import download_file, get_json
from cheburnet.app.core.paths import app_data_dir, app_root
from cheburnet.app.core.system import IS_WINDOWS

Progress = Callable[[str], None]


@dataclass(slots=True)
class VersionInfo:
    name: str
    current: str
    latest: str
    detail: str = ""
    status: str = "neutral"


@dataclass(slots=True)
class PreparedUpdate:
    tag: str
    staging_dir: Path
    exe_path: Path


def normalize_version(value: str) -> tuple[int, ...]:
    text = value.strip().lower().removeprefix("v")
    parts: list[int] = []
    for chunk in text.replace("-", ".").split("."):
        if not chunk.isdigit():
            break
        parts.append(int(chunk))
    return tuple(parts or [0])


def is_newer_version(latest: str, current: str = APP_VERSION) -> bool:
    return normalize_version(latest) > normalize_version(current)


class SelfUpdateService:
    def latest_release(self) -> dict[str, Any]:
        return get_json(CHEBURNET_RELEASE_API, timeout=20)

    def version_info(self) -> VersionInfo:
        release = self.latest_release()
        latest = str(release.get("tag_name") or release.get("name") or "").strip()
        if not latest:
            return VersionInfo(APP_NAME, APP_VERSION, "", "Релиз найден, но версия не указана", "error")
        if is_newer_version(latest, APP_VERSION):
            if not self._pick_asset(release.get("assets", [])):
                return VersionInfo(APP_NAME, APP_VERSION, latest, "Нет zip-архива Windows x64", "error")
            return VersionInfo(APP_NAME, APP_VERSION, latest, f"Доступно {latest}", "warn")
        return VersionInfo(APP_NAME, APP_VERSION, latest, "Актуально", "ok")

    def prepare_update(self, progress: Progress | None = None) -> PreparedUpdate:
        if not IS_WINDOWS:
            raise RuntimeError("Самообновление CheburNet сейчас доступно только для Windows-сборки.")
        if not getattr(sys, "frozen", False):
            raise RuntimeError("Самообновление доступно только в собранной версии CheburNet.")

        release = self.latest_release()
        latest = str(release.get("tag_name") or release.get("name") or "latest").strip()
        if latest and not is_newer_version(latest, APP_VERSION):
            raise RuntimeError("Установлена актуальная версия CheburNet.")
        asset = self._pick_asset(release.get("assets", []))
        if not asset:
            raise RuntimeError("В релизе CheburNet не найден zip-архив для Windows x64.")

        updates = self._updates_dir()
        work_dir = updates / f"CheburNet-{latest or int(time.time())}"
        archive_path = updates / str(asset["name"])
        if work_dir.exists():
            shutil.rmtree(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        download_file(str(asset["browser_download_url"]), archive_path, progress)
        extract_archive(archive_path, work_dir)
        archive_path.unlink(missing_ok=True)
        staging = self._find_staging_root(work_dir)
        exe = staging / "CheburNet.exe"
        if not exe.exists():
            raise RuntimeError("В архиве обновления не найден CheburNet.exe.")
        self.cleanup_old_updates(keep=3)
        if progress:
            progress(f"CheburNet подготовлен к обновлению: {latest}")
        return PreparedUpdate(latest, staging, exe)

    def start_update_and_exit(self, prepared: PreparedUpdate) -> None:
        if not getattr(sys, "frozen", False):
            raise RuntimeError("Самообновление доступно только в собранной версии CheburNet.")
        root = app_root()
        updates = self._updates_dir()
        backup = updates / f"backup-{APP_VERSION}-{int(time.time())}"
        script = updates / "apply-cheburnet-update.ps1"
        exe_name = "CheburNet.exe"
        script.write_text(self._apply_script(os.getpid(), root, prepared.staging_dir, backup, exe_name), encoding="utf-8")
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ],
            cwd=str(updates),
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )

    def cleanup_old_updates(self, keep: int = 3) -> None:
        updates = self._updates_dir()
        entries = [path for path in updates.iterdir() if path.name.startswith(("CheburNet-", "backup-"))]
        entries.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        for path in entries[keep:]:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
        for archive in updates.glob("*.zip"):
            archive.unlink(missing_ok=True)

    @staticmethod
    def _pick_asset(assets: Any) -> dict[str, Any] | None:
        if not isinstance(assets, list):
            return None
        fallback = None
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name", "")).lower()
            if not name.endswith(".zip") or "browser_download_url" not in asset:
                continue
            if fallback is None:
                fallback = asset
            if "windows" in name and ("x64" in name or "amd64" in name):
                return asset
        return fallback

    @staticmethod
    def _find_staging_root(path: Path) -> Path:
        if (path / "CheburNet.exe").exists():
            return path
        exe = next(path.rglob("CheburNet.exe"), None)
        return exe.parent if exe else path

    @staticmethod
    def _updates_dir() -> Path:
        path = app_data_dir() / "updates"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _ps(value: Path | str | int) -> str:
        text = str(value).replace("'", "''")
        return f"'{text}'"

    def _apply_script(self, pid: int, root: Path, staging: Path, backup: Path, exe_name: str) -> str:
        pid_text = self._ps(pid)
        root_text = self._ps(root)
        staging_text = self._ps(staging)
        backup_text = self._ps(backup)
        exe_text = self._ps(exe_name)
        return f"""$ErrorActionPreference = 'Stop'
$pidToWait = [int]{pid_text}
$root = {root_text}
$staging = {staging_text}
$backup = {backup_text}
$exeName = {exe_text}
try {{
  Wait-Process -Id $pidToWait -Timeout 45 -ErrorAction SilentlyContinue
  if (Test-Path -LiteralPath $backup) {{ Remove-Item -LiteralPath $backup -Recurse -Force }}
  Move-Item -LiteralPath $root -Destination $backup -Force
  New-Item -ItemType Directory -Path $root -Force | Out-Null
  Get-ChildItem -LiteralPath $staging -Force | Copy-Item -Destination $root -Recurse -Force
  Start-Process -FilePath (Join-Path $root $exeName) -WorkingDirectory $root
}} catch {{
  if ((Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $root)) {{
    Move-Item -LiteralPath $backup -Destination $root -Force
  }}
  throw
}}
"""
