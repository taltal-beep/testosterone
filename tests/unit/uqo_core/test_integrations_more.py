"""More coverage for ``uqo_core.integrations`` (all mocked network / extractors)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uqo_core.metrics import RunMetrics


@pytest.fixture
def sample_metrics() -> RunMetrics:
    return RunMetrics(
        timestamp=1,
        total_tests=2,
        passed=2,
        failed=0,
        broken=0,
        skipped=0,
        unknown=0,
        duration_ms=10,
        run_id="rid",
    )


def test_integration_status_from_env_false(monkeypatch: pytest.MonkeyPatch) -> None:
    from uqo_core.integrations import integration_status_from_env

    monkeypatch.delenv("INFLUXDB_URL", raising=False)
    monkeypatch.delenv("INFLUXDB_TOKEN", raising=False)
    monkeypatch.delenv("INFLUXDB_ORG", raising=False)
    monkeypatch.delenv("INFLUXDB_BUCKET", raising=False)
    monkeypatch.delenv("PROMETHEUS_PUSHGATEWAY_URL", raising=False)
    st = integration_status_from_env()
    assert st["influx_configured"] is False
    assert st["prometheus_configured"] is False


def test_push_to_prometheus_missing_url(sample_metrics: RunMetrics) -> None:
    from uqo_core.integrations import push_to_prometheus

    ok, msg = push_to_prometheus(sample_metrics, pushgateway_url=None)
    assert ok is False
    assert "PROMETHEUS_PUSHGATEWAY_URL" in msg


def test_push_to_prometheus_http_error(sample_metrics: RunMetrics) -> None:
    from uqo_core.integrations import push_to_prometheus

    with patch("uqo_core.integrations.requests.post") as post:
        post.return_value = MagicMock(status_code=400, text="bad")
        ok, msg = push_to_prometheus(sample_metrics, pushgateway_url="http://x:9091", job_name="uqo")
    assert ok is False
    assert "HTTP 400" in msg


def test_auto_push_metrics_no_extract(tmp_path: Path) -> None:
    from uqo_core.integrations import auto_push_metrics_if_enabled

    with patch("uqo_core.integrations.extract_best", return_value=None):
        out = auto_push_metrics_if_enabled(
            artifacts_root=tmp_path,
            run_id="rid",
            auto_influx=True,
            auto_prometheus=True,
        )
    assert out and out[0][0] == "metrics"


def test_auto_push_metrics_happy_path(tmp_path: Path, sample_metrics: RunMetrics) -> None:
    from uqo_core.integrations import auto_push_metrics_if_enabled

    fake_em = MagicMock()
    with patch("uqo_core.integrations.extract_best", return_value=fake_em):
        with patch("uqo_core.integrations.to_run_metrics", return_value=sample_metrics):
            with patch("uqo_core.integrations.push_to_influxdb", return_value=(True, "ok")):
                with patch("uqo_core.integrations.push_to_prometheus", return_value=(True, "ok")):
                    out = auto_push_metrics_if_enabled(
                        artifacts_root=tmp_path,
                        run_id="rid",
                        auto_influx=True,
                        auto_prometheus=True,
                        prometheus_pushgateway_url="http://x:9091",
                    )
    targets = [t for t, _ok, _msg in out]
    assert "influxdb" in targets
    assert "prometheus" in targets

