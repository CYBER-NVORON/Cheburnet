from __future__ import annotations

import urllib.error

from cheburnet.app.models.health import HealthCheckResult, HealthStatus
from cheburnet.app.models.profile import Profile
from cheburnet.app.services.healthcheck_service import HealthcheckService


def test_tcp_check_requires_host_and_port() -> None:
    result = HealthcheckService().tcp_check(Profile(id="p", name="bad", protocol="vless"))

    assert result.status == "syntax_error"


def test_vpn_ready_retries_before_success() -> None:
    class RetryHealthcheck(HealthcheckService):
        def __init__(self) -> None:
            self.calls = 0

        def internet_check(self, timeout: float = 10.0) -> HealthCheckResult:
            self.calls += 1
            if self.calls == 1:
                return HealthCheckResult("internet", HealthStatus.TIMEOUT, "Таймаут проверки")
            return HealthCheckResult("internet", HealthStatus.OK, "HTTP 204", 42)

    service = RetryHealthcheck()
    result = service.check_vpn_ready(Profile(id="p", name="ok", protocol="vless"), attempts=2, delay=0)

    assert result.status == "online"
    assert result.latency_ms == 42
    assert service.calls == 2


def test_http_check_treats_http_error_under_500_as_reachable(monkeypatch) -> None:
    def raise_forbidden(*_args, **_kwargs):
        raise urllib.error.HTTPError("https://example.com", 403, "Forbidden", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", raise_forbidden)

    result = HealthcheckService().http_check("https://example.com")

    assert result.status == HealthStatus.OK
    assert result.detail == "HTTP 403"
