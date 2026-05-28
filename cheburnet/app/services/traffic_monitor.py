from __future__ import annotations

import time
from collections.abc import Callable

CounterReader = Callable[[], tuple[int, int]]
Clock = Callable[[], float]


class TrafficMonitor:
    def __init__(
        self,
        counter_reader: CounterReader | None = None,
        clock: Clock | None = None,
        history_limit: int = 60,
    ) -> None:
        self.counter_reader = counter_reader or self._psutil_counters
        self.clock = clock or time.time
        self.history_limit = history_limit
        self.previous: tuple[float, int, int] | None = None
        self.points: list[tuple[float, float]] = []

    def sample(self, active: bool) -> dict[str, object]:
        if not active:
            self.previous = None
            self.points.clear()
            return self._unavailable("VPN отключен")

        try:
            received, sent = self.counter_reader()
        except Exception as exc:
            self.previous = None
            self.points.clear()
            return self._unavailable(f"Нет данных: {exc}")

        now = self.clock()
        if self.previous is None:
            self.previous = (now, received, sent)
            return self._available(0.0, 0.0)

        previous_time, previous_received, previous_sent = self.previous
        elapsed = max(now - previous_time, 0.001)
        received_delta = max(received - previous_received, 0)
        sent_delta = max(sent - previous_sent, 0)
        self.previous = (now, received, sent)

        download_mbps = received_delta * 8 / elapsed / 1_000_000
        upload_mbps = sent_delta * 8 / elapsed / 1_000_000
        return self._available(download_mbps, upload_mbps)

    def _available(self, download_mbps: float, upload_mbps: float) -> dict[str, object]:
        self.points.append((download_mbps, upload_mbps))
        self.points = self.points[-self.history_limit :]
        return {
            "available": True,
            "download_mbps": download_mbps,
            "upload_mbps": upload_mbps,
            "points": list(self.points),
            "message": "",
        }

    @staticmethod
    def _unavailable(message: str) -> dict[str, object]:
        return {"available": False, "download_mbps": 0.0, "upload_mbps": 0.0, "points": [], "message": message}

    @staticmethod
    def _psutil_counters() -> tuple[int, int]:
        try:
            import psutil
        except ImportError as exc:
            raise RuntimeError("установите psutil") from exc
        counters = psutil.net_io_counters()
        return int(counters.bytes_recv), int(counters.bytes_sent)
