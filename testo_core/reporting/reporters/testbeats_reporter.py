"""TestBeats notifications via Slack Block Kit or Teams Adaptive Cards."""

from __future__ import annotations

import json
from pathlib import Path

import requests

from testo_core.reporting.allure_results import parse_collected_results
from testo_core.reporting.collector import CollectedResults
from testo_core.reporting.exporter import write_json_summary
from testo_core.reporting.reporters.base import BaseReporter, ReportContext, ReporterResult
from testo_core.reporting.reporters.testbeats_payloads import (
    build_slack_payload,
    build_teams_payload,
)


class TestBeatsReporter(BaseReporter):
    @property
    def reporter_type(self) -> str:
        return "testbeats"

    def publish(
        self,
        *,
        results: CollectedResults,
        context: ReportContext,
        console: object | None = None,
    ) -> ReporterResult:
        slack_url = (self._options.get("slack_webhook") or "").strip()
        teams_url = (self._options.get("teams_webhook") or "").strip()
        channel = (self._options.get("channel") or "").strip()
        title = (self._options.get("title") or "").strip() or None
        report_url = (self._options.get("report_url") or "").strip() or None

        if not results.stages:
            return ReporterResult(ok=False, message="no results to publish via TestBeats.")

        out_dir = context.artifacts_root / "reports" / "testbeats"
        out_dir.mkdir(parents=True, exist_ok=True)
        summary_path = out_dir / "summary.json"
        write_json_summary(results=results, out=summary_path)

        aggregate = parse_collected_results(results)
        slack_payload = build_slack_payload(
            aggregate,
            context=context,
            channel=channel,
            title=title,
            report_url=report_url,
        )
        teams_payload = build_teams_payload(
            aggregate,
            context=context,
            channel=channel,
            title=title,
            report_url=report_url,
        )

        preview_path = out_dir / "notification_preview.json"
        preview_path.write_text(
            json.dumps({"slack": slack_payload, "teams": teams_payload}, indent=2),
            encoding="utf-8",
        )

        artifacts: list[Path] = [summary_path, preview_path]
        errors: list[str] = []

        if not slack_url and not teams_url:
            msg = f"TestBeats preview at {preview_path} (set slack_webhook or teams_webhook to send)"
            if console is not None:
                console.print(f"[muted]{msg}[/]")  # type: ignore[union-attr]
            return ReporterResult(ok=True, message=msg, artifacts=tuple(artifacts))

        if slack_url:
            ok, err = _post_json(slack_url, slack_payload)
            if ok:
                (out_dir / "slack_sent.marker").write_text("ok", encoding="utf-8")
                artifacts.append(out_dir / "slack_sent.marker")
            else:
                errors.append(f"slack: {err}")

        if teams_url:
            ok, err = _post_json(teams_url, teams_payload)
            if ok:
                (out_dir / "teams_sent.marker").write_text("ok", encoding="utf-8")
                artifacts.append(out_dir / "teams_sent.marker")
            else:
                errors.append(f"teams: {err}")

        if errors:
            return ReporterResult(ok=False, message="; ".join(errors))

        msg = "TestBeats notification sent."
        if console is not None:
            console.print(f"[ok]{msg}[/]")  # type: ignore[union-attr]
        return ReporterResult(ok=True, message=msg, artifacts=tuple(artifacts))


def _post_json(url: str, payload: dict) -> tuple[bool, str]:
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code >= 400:
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        return True, ""
    except requests.RequestException as exc:
        return False, str(exc)
