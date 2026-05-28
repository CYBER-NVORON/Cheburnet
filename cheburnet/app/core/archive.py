from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path


def _safe_target(root: Path, name: str) -> Path:
    target = (root / name).resolve()
    root_resolved = root.resolve()
    if root_resolved != target and root_resolved not in target.parents:
        raise RuntimeError(f"Архив содержит небезопасный путь: {name}")
    return target


def extract_archive(archive_path: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    lower = archive_path.name.lower()
    if lower.endswith(".zip"):
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.namelist():
                _safe_target(destination, member)
            archive.extractall(destination)
        return destination
    if lower.endswith(".tar.gz") or lower.endswith(".tgz") or lower.endswith(".tar"):
        with tarfile.open(archive_path) as archive:
            for member in archive.getmembers():
                _safe_target(destination, member.name)
            archive.extractall(destination)
        return destination
    raise RuntimeError(f"Неподдерживаемый архив: {archive_path.name}")
