"""Post-mortem Rich panel for a finished stage + plan summary table."""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


@dataclass(frozen=True)
class StagePanelData:
    """Data needed to render the post-mortem panel for a finished stage."""

    name: str
    framework: str
    returncode: int
    duration_s: float
    log_path: str | None
    output_tail: str
    command: str | None = None


def render_stage_panel(console: Console, data: StagePanelData, *, tail_max_lines: int = 80) -> None:
    """Render a single stage panel to ``console``."""
    status_label = "PASS" if data.returncode == 0 else f"FAIL ({data.returncode})"
    style = "ok" if data.returncode == 0 else "fail"

    title = Text.from_markup(
        f"[{style}]{data.name}[/] [framework]({data.framework})[/] [{style}]{status_label}[/]"
    )

    rows: list[object] = []
    rows.append(Text.from_markup(f"[muted]duration:[/] {data.duration_s:.2f}s"))
    if data.command:
        rows.append(Text.from_markup(f"[muted]command:[/]  {data.command}"))
    rows.append(Text.from_markup(f"[muted]log:[/]      {data.log_path or '<buffered>'}"))

    tail = data.output_tail.rstrip("\n")
    if tail:
        lines = tail.splitlines()
        if len(lines) > tail_max_lines:
            omitted = len(lines) - tail_max_lines
            lines = [f"... ({omitted} earlier lines omitted)", *lines[-tail_max_lines:]]
        rows.append(Text(""))
        rows.append(Text("--- output tail ---", style="muted"))
        rows.append(Text("\n".join(lines)))

    console.print(Panel(Group(*rows), title=title, border_style=style, expand=True))


def render_plan_summary(
    console: Console,
    *,
    plan_name: str,
    stage_results: list[StagePanelData],
    aggregate_returncode: int,
) -> None:
    """Render a final table summarising every stage in the plan."""
    style = "ok" if aggregate_returncode == 0 else "fail"
    table = Table(
        title=Text.from_markup(f"[{style}]Plan summary — {plan_name}[/]"),
        show_lines=False,
        title_justify="left",
    )
    table.add_column("Stage", style="title")
    table.add_column("Framework", style="framework")
    table.add_column("Status")
    table.add_column("Duration", justify="right")
    for stage in stage_results:
        status = "[ok]PASS[/]" if stage.returncode == 0 else f"[fail]FAIL ({stage.returncode})[/]"
        table.add_row(stage.name, stage.framework, status, f"{stage.duration_s:.2f}s")
    console.print(table)
