"""Extract archived cycles, inject baseline Allure ``history/``, then ``allure serve`` current results."""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from rich.console import Console

from testo_core.reporting.allure import AllureCLINotFoundError, generate_html, serve_results
from testo_core.reporting.allure_delta_transform import apply_delta_first_mutations
from testo_core.reporting.allure_summary_widgets import write_summary_comparison_sidecars
from testo_core.reporting.collector import collect_results
from testo_core.repository.models import ReportArchive
from testo_core.services.report_archive import extract_archive_to_plan_dir
from testo_core.services.report_archive_diff import count_regression_and_fix_between_plans

logger = logging.getLogger(__name__)


def _inject_history_from_report(*, history_src: Path, current_result_dirs: list[Path]) -> bool:
    if not history_src.is_dir():
        return False
    copied = False
    for dest_parent in current_result_dirs:
        dest = dest_parent / "history"
        shutil.copytree(history_src, dest, dirs_exist_ok=True)
        copied = True
    return copied


def run_summary_allure_pipeline(
    *,
    baseline: ReportArchive | None,
    current: ReportArchive,
    console: Console,
    serve: bool = True,
) -> None:
    """Extract zips, optionally build history from baseline report, then ``allure serve`` or static HTML."""
    con = console

    try:
        with tempfile.TemporaryDirectory(prefix="testo-allure-summary-") as td_raw:
            root = Path(td_raw)
            baseline_root = root / "baseline_extract"
            current_root = root / "current_extract"
            baseline_report = root / "baseline_report"
            static_out = root / "compare_html"

            extract_archive_to_plan_dir(
                zip_bytes=current.artifact_bytes,
                dest_artifacts_root=current_root,
                plan_name=current.cycle_name,
            )
            if baseline is not None:
                extract_archive_to_plan_dir(
                    zip_bytes=baseline.artifact_bytes,
                    dest_artifacts_root=baseline_root,
                    plan_name=baseline.cycle_name,
                )

            cur_collected = collect_results(current_root, plan_name=current.cycle_name)
            current_dirs = cur_collected.result_dirs

            if not current_dirs:
                con.print("[dim]No Allure result directories in the current archive; skipping Allure serve.[/]")
                return

            current_plan = current_root / current.cycle_name
            regressions, fixes = (0, 0)
            perf_md: str | None = None
            if baseline is not None:
                baseline_plan = baseline_root / baseline.cycle_name
                if baseline_plan.is_dir() and current_plan.is_dir():
                    try:
                        stats = apply_delta_first_mutations(
                            baseline_plan_root=baseline_plan,
                            current_plan_root=current_plan,
                        )
                        perf_md = stats.performance_summary_md or None
                    except Exception:
                        logger.exception("Delta-first Allure mutation failed")
                    try:
                        regressions, fixes = count_regression_and_fix_between_plans(
                            baseline_plan,
                            current_plan,
                        )
                    except OSError:
                        logger.exception("Failed to count regressions/fixes for Allure comparison metadata")

            write_summary_comparison_sidecars(
                result_dirs=current_dirs,
                baseline=baseline,
                current=current,
                regressions_found=regressions,
                fixes_verified=fixes,
                performance_summary_md=perf_md,
            )

            history_src: Path | None = None
            if baseline is not None:
                base_collected = collect_results(baseline_root, plan_name=baseline.cycle_name)
                baseline_dirs = base_collected.result_dirs
                if baseline_dirs:
                    gen = generate_html(
                        result_dirs=baseline_dirs,
                        out_dir=baseline_report,
                        clean=True,
                    )
                    if gen.ok and (baseline_report / "history").is_dir():
                        history_src = baseline_report / "history"
                    else:
                        con.print(
                            f"[dim]Baseline Allure generate did not produce history ({gen.message}); "
                            "serving current results without injected history.[/]"
                        )
                else:
                    con.print("[dim]No Allure results in baseline archive; serving current without history.[/]")

            if history_src is not None:
                _inject_history_from_report(
                    history_src=history_src,
                    current_result_dirs=current_dirs,
                )

            if serve:
                con.print("[ok]Done. Opening Allure...[/]")
                serve_results(result_dirs=current_dirs, port=8080)
            else:
                gen_cur = generate_html(result_dirs=current_dirs, out_dir=static_out, clean=True)
                if gen_cur.ok:
                    idx = (static_out / "index.html").resolve()
                    con.print("[ok]Comparison HTML generated (--no-open).[/]")
                    con.print(f"[muted]index.html[/] [link={idx.as_uri()}]{idx}[/]")
                else:
                    con.print(f"[fail]allure generate failed:[/] {gen_cur.message}")
    except AllureCLINotFoundError as exc:
        con.print(f"[fail]{exc}[/]")
    except Exception:
        logger.exception("Allure summary serve pipeline failed")
        con.print("[fail]Allure visual report step failed (see logs).[/]")
