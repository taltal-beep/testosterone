from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from .metrics import RunMetrics, push_influxdb as _push_influx_core
from .metrics_extractor import ExtractedMetrics, extract_best, to_run_metrics
from .report_generator import default_report_paths


def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is not None and str(v).strip() != "":
        return str(v).strip()
    return default


def influx_settings_from_env() -> dict[str, str | None]:
    return {
        "url": _env("INFLUXDB_URL"),
        "token": _env("INFLUXDB_TOKEN"),
        "org": _env("INFLUXDB_ORG"),
        "bucket": _env("INFLUXDB_BUCKET"),
    }


def prometheus_settings_from_env() -> dict[str, str | None]:
    return {
        "pushgateway_url": _env("PROMETHEUS_PUSHGATEWAY_URL"),
        "job_name": _env("PROMETHEUS_JOB_NAME", "uqo"),
    }


def push_to_influxdb(
    metrics: RunMetrics,
    *,
    url: str | None = None,
    token: str | None = None,
    org: str | None = None,
    bucket: str | None = None,
    measurement: str = "uqo_test_run",
) -> tuple[bool, str]:
    """
    Push metrics to InfluxDB. When arguments are omitted, reads ``INFLUXDB_*`` from the environment
    (typically loaded from ``.env``).
    """
    try:
        s = influx_settings_from_env()
        u = url or s["url"]
        t = token or s["token"]
        o = org or s["org"]
        b = bucket or s["bucket"]
        if not u or not t or not o or not b:
            return False, "InfluxDB: set INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG, and INFLUXDB_BUCKET (e.g. in .env)."
        return _push_influx_core(metrics, url=u, token=t, org=o, bucket=b, measurement=measurement)
    except Exception as exc:
        return False, f"InfluxDB push error: {exc}"


def _escape_prom_label_value(s: str) -> str:
    return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _prometheus_exposition(metrics: RunMetrics) -> str:
    """OpenMetrics-style text for Pushgateway."""
    rid = _escape_prom_label_value(metrics.run_id or "unknown")
    lines = [
        "# HELP uqo_total_tests Total test cases in Allure aggregate",
        "# TYPE uqo_total_tests gauge",
        f'uqo_total_tests{{run_id="{rid}"}} {int(metrics.total_tests)}',
        "# HELP uqo_passed Passed tests",
        "# TYPE uqo_passed gauge",
        f'uqo_passed{{run_id="{rid}"}} {int(metrics.passed)}',
        "# HELP uqo_failed Failed tests",
        "# TYPE uqo_failed gauge",
        f'uqo_failed{{run_id="{rid}"}} {int(metrics.failed)}',
        "# HELP uqo_duration_ms Aggregate span (ms)",
        "# TYPE uqo_duration_ms gauge",
        f'uqo_duration_ms{{run_id="{rid}"}} {int(metrics.duration_ms)}',
    ]
    return "\n".join(lines) + "\n"


def push_to_prometheus(
    metrics: RunMetrics,
    *,
    pushgateway_url: str | None = None,
    job_name: str | None = None,
) -> tuple[bool, str]:
    """
    Push metrics to a Prometheus Pushgateway (``POST /metrics/job/<job>``).
    Uses ``PROMETHEUS_PUSHGATEWAY_URL`` and ``PROMETHEUS_JOB_NAME`` from the environment when omitted.
    """
    try:
        s = prometheus_settings_from_env()
        base = (pushgateway_url or s["pushgateway_url"] or "").rstrip("/")
        job = job_name or s["job_name"] or "uqo"
        if not base:
            return False, "Prometheus: set PROMETHEUS_PUSHGATEWAY_URL (e.g. http://localhost:9091)."
        url = f"{base}/metrics/job/{quote(job, safe='')}"
        body = _prometheus_exposition(metrics)
        r = requests.post(url, data=body.encode("utf-8"), headers={"Content-Type": "text/plain; charset=utf-8"}, timeout=15)
        if r.status_code >= 400:
            return False, f"Pushgateway HTTP {r.status_code}: {(r.text or '')[:500]}"
        return True, "Pushed metrics to Prometheus Pushgateway."
    except Exception as exc:
        return False, f"Prometheus push error: {exc}"


def test_influxdb_connection(
    *,
    url: str | None = None,
    token: str | None = None,
    org: str | None = None,
) -> tuple[bool, str]:
    try:
        s = influx_settings_from_env()
        u = url or s["url"]
        t = token or s["token"]
        o = org or s["org"]
        if not u or not t or not o:
            return False, "Missing INFLUXDB_URL, INFLUXDB_TOKEN, or INFLUXDB_ORG."
        from influxdb_client import InfluxDBClient  # type: ignore

        client = InfluxDBClient(url=u, token=t, org=o, timeout=10_000)
        try:
            ping = getattr(client, "ping", None)
            if callable(ping):
                try:
                    ping()
                except Exception:
                    h = client.health()
                    st = getattr(h, "status", "")
                    if st and str(st).lower() != "pass":
                        return False, f"InfluxDB health: {h}"
            else:
                h = client.health()
                st = getattr(h, "status", "")
                if st and str(st).lower() != "pass":
                    return False, f"InfluxDB health: {h}"
        finally:
            client.close()
        return True, "InfluxDB: connection OK."
    except Exception as exc:
        return False, f"InfluxDB test failed: {exc}"


def test_prometheus_pushgateway(*, pushgateway_url: str | None = None) -> tuple[bool, str]:
    try:
        s = prometheus_settings_from_env()
        base = (pushgateway_url or s["pushgateway_url"] or "").rstrip("/")
        if not base:
            return False, "Prometheus: set PROMETHEUS_PUSHGATEWAY_URL."
        for path in ("/-/healthy", "/metrics", "/"):
            try:
                r = requests.get(f"{base}{path}", timeout=10)
                if r.status_code < 500:
                    return True, "Pushgateway: reachable."
            except Exception:
                continue
        return False, "Pushgateway: could not reach endpoint."
    except Exception as exc:
        return False, f"Prometheus test failed: {exc}"


def auto_push_metrics_if_enabled(
    *,
    artifacts_root: Path,
    run_id: str | None,
    auto_influx: bool,
    auto_prometheus: bool,
    influx_url: str | None = None,
    influx_token: str | None = None,
    influx_org: str | None = None,
    influx_bucket: str | None = None,
    prometheus_pushgateway_url: str | None = None,
) -> list[tuple[str, bool, str]]:
    """
    Best-effort metrics extraction + push after a run. Never raises; returns a list of
    ``(target, ok, message)`` for UI logging.

    Optional Influx/Prometheus parameters override ``.env`` for this push (Streamlit session).
    """
    out: list[tuple[str, bool, str]] = []
    try:
        ar = artifacts_root.expanduser().resolve()
        paths = default_report_paths(artifacts_root=ar)
        em: ExtractedMetrics | None = extract_best(
            report_dir=paths.report_dir,
            results_dir=paths.results_dir,
        )
        if em is None:
            out.append(("metrics", False, "No Allure report/results to extract."))
            return out
        rm = to_run_metrics(em, run_id=run_id)
        if auto_influx:
            try:
                ok, msg = push_to_influxdb(
                    rm,
                    url=influx_url,
                    token=influx_token,
                    org=influx_org,
                    bucket=influx_bucket,
                )
                out.append(("influxdb", ok, msg))
            except Exception as exc:
                out.append(("influxdb", False, str(exc)))
        if auto_prometheus:
            try:
                ok, msg = push_to_prometheus(rm, pushgateway_url=prometheus_pushgateway_url)
                out.append(("prometheus", ok, msg))
            except Exception as exc:
                out.append(("prometheus", False, str(exc)))
    except Exception as exc:
        out.append(("auto_push", False, str(exc)))
    return out


def integration_status_from_env() -> dict[str, Any]:
    """Lightweight readiness flags for UI (no network by default)."""
    inf = influx_settings_from_env()
    pr = prometheus_settings_from_env()
    return {
        "influx_configured": bool(inf["url"] and inf["token"] and inf["org"] and inf["bucket"]),
        "prometheus_configured": bool(pr["pushgateway_url"]),
    }
