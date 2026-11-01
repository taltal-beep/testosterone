"""``testo notify`` — send a recorded run to Slack and/or Microsoft Teams."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import typer

from testo_core.engine.exit_codes import EngineExitCode

if TYPE_CHECKING:
    from testo_core.services import run_alerts


def notify(
    to: list[str] = typer.Option(
        ...,
        "--to",
        help="slack or teams; repeat for both. URLs come from $TESTO_SLACK_WEBHOOK_URL "
        "and $TESTO_TEAMS_WEBHOOK_URL.",
    ),
    cycle: str | None = typer.Option(
        None, "--cycle", help="Latest run of this cycle (with --digest: only this cycle)."
    ),
    run_id: str | None = typer.Option(None, "--run-id", help="A specific run (run-history id)."),
    when: str = typer.Option(
        "failure",
        "--when",
        help="failure: red run or newly flaky test. change: differs from the previous run. "
        "always: every run.",
    ),
    title: str | None = typer.Option(None, "--title", help="Name in the message (default: cycle)."),
    run_url: str | None = typer.Option(
        None,
        "--run-url",
        help="'View run' link, e.g. the CI run that produced it (with --digest: your UI's URL).",
    ),
    digest: str | None = typer.Option(
        None,
        "--digest",
        help="day or week: send a digest of every cycle's runs over that period instead of "
        "one run (newly flaky, fixed, still failing, slower). Run it from cron or a "
        "scheduled CI job.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print the JSON payloads instead of sending them."
    ),
) -> None:
    """Send the run (failing tests, regressions, newly flaky tests), or a digest, to chat webhooks."""
    import json

    from testo_core.services import run_alerts

    if digest is not None:
        _send_digest(to=to, period=digest, cycle=cycle, run_id=run_id, url=run_url, dry_run=dry_run)
    channels = [c.strip().lower() for c in to]
    bad = [c for c in channels if c not in run_alerts.CHANNELS]
    if bad or when not in run_alerts.WHEN_CHOICES:
        typer.echo(
            f"--to takes {' / '.join(run_alerts.CHANNELS)} and --when takes "
            f"{' / '.join(run_alerts.WHEN_CHOICES)}",
            err=True,
        )
        raise typer.Exit(code=int(EngineExitCode.INVALID_INPUT))
    targets = cast("list[run_alerts.AlertChannel]", list(dict.fromkeys(channels)))
    urls = _webhooks(targets, dry_run=dry_run)

    alert = run_alerts.load_alert(cycle=cycle.strip() if cycle else None, run_id=run_id)
    if alert is None:
        typer.echo("no recorded run found", err=True)
        raise typer.Exit(code=int(EngineExitCode.INVALID_INPUT))
    if not run_alerts.should_send(alert, cast("run_alerts.AlertWhen", when)):
        typer.echo(f"nothing to report (--when {when})", err=True)
        raise typer.Exit(code=0)

    failed = False
    for channel in targets:
        payload = run_alerts.build_payload(channel, alert, title=title, run_url=run_url)
        if dry_run:
            typer.echo(json.dumps({channel: payload}, indent=2, ensure_ascii=False))
            continue
        try:
            run_alerts.post(urls[channel], payload)
        except run_alerts.AlertError as exc:
            typer.echo(f"{channel}: {exc}", err=True)
            failed = True
        else:
            typer.echo(f"{channel}: sent", err=True)
    raise typer.Exit(code=int(EngineExitCode.INFRA_FAILURE) if failed else 0)


def _webhooks(
    targets: list[run_alerts.AlertChannel], *, dry_run: bool
) -> dict[run_alerts.AlertChannel, str]:
    from testo_core.services import run_alerts

    urls = {c: run_alerts.webhook_from_env(c) for c in targets}
    missing = [run_alerts.WEBHOOK_ENV[c] for c, url in urls.items() if not url]
    if missing and not dry_run:
        typer.echo(f"not set: {', '.join(missing)}", err=True)
        raise typer.Exit(code=int(EngineExitCode.INVALID_INPUT))
    return urls


def _send_digest(
    *,
    to: list[str],
    period: str,
    cycle: str | None,
    run_id: str | None,
    url: str | None,
    dry_run: bool,
) -> None:
    import json

    from testo_core.services import run_alerts, run_digest

    channels = [c.strip().lower() for c in to]
    bad = [c for c in channels if c not in run_alerts.CHANNELS]
    if bad or period not in run_digest.PERIODS or run_id:
        typer.echo(
            f"--to takes {' / '.join(run_alerts.CHANNELS)}, --digest takes "
            f"{' / '.join(run_digest.PERIODS)}, and --digest doesn't take --run-id",
            err=True,
        )
        raise typer.Exit(code=int(EngineExitCode.INVALID_INPUT))
    targets = cast("list[run_alerts.AlertChannel]", list(dict.fromkeys(channels)))
    urls = _webhooks(targets, dry_run=dry_run)
    report = run_digest.build_digest(
        period=period, cycles=[cycle.strip()] if cycle and cycle.strip() else None
    )
    if not report.cycles:
        typer.echo(f"nothing to report: no runs in the last {period}", err=True)
        raise typer.Exit(code=0)
    failed = False
    for channel in targets:
        payload = run_digest.build_payload(channel, report, url=url)
        if dry_run:
            typer.echo(json.dumps({channel: payload}, indent=2, ensure_ascii=False))
            continue
        try:
            run_alerts.post(urls[channel], payload)
        except run_alerts.AlertError as exc:
            typer.echo(f"{channel}: {exc}", err=True)
            failed = True
        else:
            typer.echo(f"{channel}: digest sent", err=True)
    raise typer.Exit(code=int(EngineExitCode.INFRA_FAILURE) if failed else 0)
