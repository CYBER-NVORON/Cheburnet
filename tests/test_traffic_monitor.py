from __future__ import annotations

from cheburnet.app.services.traffic_monitor import TrafficMonitor


def test_traffic_monitor_rates_from_network_counters() -> None:
    counters = iter([(1_000_000, 2_000_000), (2_000_000, 2_500_000)])
    times = iter([100.0, 101.0])

    monitor = TrafficMonitor(counter_reader=lambda: next(counters), clock=lambda: next(times))

    first = monitor.sample(active=True)
    second = monitor.sample(active=True)

    assert first["available"] is True
    assert first["download_mbps"] == 0.0
    assert first["upload_mbps"] == 0.0
    assert second["available"] is True
    assert second["download_mbps"] == 8.0
    assert second["upload_mbps"] == 4.0


def test_traffic_monitor_resets_when_inactive() -> None:
    monitor = TrafficMonitor(counter_reader=lambda: (1_000_000, 2_000_000), clock=lambda: 100.0)

    sample = monitor.sample(active=False)

    assert sample["available"] is False
    assert sample["points"] == []
