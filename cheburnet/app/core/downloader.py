from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any, Callable

Progress = Callable[[str], None]


def get_json(url: str, timeout: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "CheburNet/0.2"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_text(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "CheburNet/0.2"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def download_file(url: str, destination: Path, progress: Progress | None = None) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if progress:
        progress(f"Скачиваю {destination.name}")
    request = urllib.request.Request(url, headers={"User-Agent": "CheburNet/0.2"})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as file:
        file.write(response.read())
    return destination
