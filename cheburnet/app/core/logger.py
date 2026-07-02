from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Callable

from cheburnet.app.core.paths import logs_dir

LogSink = Callable[[str], None]

UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
KEY_RE = re.compile(r"(?i)(private_key|privatekey|password|token|secret)(\s*[:=]\s*)([^,\s\"']+)")


def mask_sensitive(text: str) -> str:
    def mask_uuid(match: re.Match[str]) -> str:
        value = match.group(0)
        return f"{value[:4]}...{value[-4:]}"

    text = UUID_RE.sub(mask_uuid, text)
    text = KEY_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)
    return text


class AppLogger:
    def __init__(self, sink: LogSink | None = None, path: Path | None = None) -> None:
        self.sink = sink
        self.path = path or logs_dir() / "cheburnet.log"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._pending: list[str] = []
        self._last_flush = time.time()
        self._flush_interval = 1.0
        self._flush_limit = 20
        self._trim_log()

    def bind(self, sink: LogSink) -> None:
        self.sink = sink

    def debug(self, message: str) -> None:
        self._write("DEBUG", message)

    def info(self, message: str) -> None:
        self._write("INFO", message)

    def warning(self, message: str) -> None:
        self._write("WARNING", message)

    def error(self, message: str) -> None:
        self._write("ERROR", message)

    def _write(self, level: str, message: str) -> None:
        safe = mask_sensitive(str(message).rstrip())
        if not safe:
            return
        line = f"{time.strftime('%H:%M:%S')}  {level:<7} {safe}"
        self._pending.append(line)
        if level == "ERROR" or len(self._pending) >= self._flush_limit or time.time() - self._last_flush >= self._flush_interval:
            self.flush()
        if self.sink:
            self.sink(line)

    def flush(self) -> None:
        if not self._pending:
            return
        lines = self._pending
        self._pending = []
        self._last_flush = time.time()
        try:
            with self.path.open("a", encoding="utf-8") as file:
                file.write("\n".join(lines) + "\n")
        except OSError:
            pass

    def _trim_log(self, max_bytes: int = 2_000_000) -> None:
        try:
            if self.path.exists() and self.path.stat().st_size > max_bytes:
                text = self.path.read_text(encoding="utf-8", errors="replace")
                self.path.write_text("\n".join(text.splitlines()[-2000:]) + "\n", encoding="utf-8")
        except OSError:
            pass
