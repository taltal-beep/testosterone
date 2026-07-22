from __future__ import annotations

import contextlib
import http.server
import os
import shutil
import socket
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import (
    ORCHESTRATOR_ROOT,
    STATIC_ALLURE_HTML,
    STATIC_ALLURE_INDEX,
    STATIC_ALLURE_REPORT_DIR,
    STATIC_ALLURE_REPORTS_DIR,
    STATIC_BEHAVE_DIR,
    STATIC_BEHAVE_INDEX,
    STATIC_DIR,
    allure_report_dir,
)


def _flatten_allure_result_json(*, root: Path) -> int:
    """
    BehaveX sometimes writes Allure results under a nested folder (e.g. ``behave/allure``).
    To ensure the Allure CLI always finds JSON without relying on recursive scanning behavior,
    move any nested ``*-result.json`` files up into ``root``.

    Returns the number of files moved.
    """
    root = root.expanduser().resolve()
    if not root.is_dir():
        return 0

    moved = 0
    try:
        for p in root.rglob("*-result.json"):
            if p.parent == root:
                continue
            dest = root / p.name
            if dest.exists():
                # Avoid overwriting; keep the nested copy in place if collision happens.
                continue
            try:
                p.replace(dest)
                moved += 1
            except OSError:
                continue
    except OSError:
        return 0
    return moved


@dataclass(frozen=True)
class ReportPaths:
    results_dir: Path
    report_dir: Path
    zip_path: Path


def _invoke_allure_generate(
    *,
    result_dirs: list[Path],
    report_dir: Path,
    single_file: bool,
    subprocess_run: Callable[..., Any] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Thin wrapper so tests can inject ``subprocess_run`` without patching ``subprocess``."""
    from testo_core.reporting.allure_cli import run_generate

    return run_generate(
        result_dirs=result_dirs,
        out_dir=report_dir,
        clean=True,
        single_file=single_file,
        subprocess_run=subprocess_run,
    )


def compute_system_health_pct(results_dir: Path) -> float | None:
    """
    Overall pass rate from Allure ``*-result.json`` files under ``results_dir``:
    ``100.0 * passed / total`` (tests with status ``passed`` vs all result files).
    """
    from .metrics import parse_allure_results_dir

    results_dir = results_dir.expanduser().resolve()
    if not results_dir.is_dir():
        return None
    m = parse_allure_results_dir(results_dir)
    if m.total_tests <= 0:
        return None
    return (m.passed / m.total_tests) * 100.0


def generate_allure_html(
    *,
    results_dir: Path,
    report_dir: Path,
    input_dirs: list[Path] | None = None,
    subprocess_run: Callable[..., Any] | None = None,
) -> tuple[bool, str, float | None]:
    """
    Generate Allure HTML via Allure Report 3 (Node.js CLI):
      ``allure awesome --single-file`` or ``allure generate`` with ``allurerc.mjs``.

    Each report is generated from an isolated framework-specific results directory.

    Returns ``(ok, message, health_pct)`` where ``health_pct`` is passed/total from result JSON files.

    Requires Node.js 18+ and ``npm install`` in the repo root (or ``TESTO_ALLURE_BIN``).
    """
    results_dir = results_dir.expanduser().resolve()
    report_dir = report_dir.expanduser().resolve()

    if not results_dir.exists():
        return False, f"Results dir does not exist: {results_dir}", None

    # Each report MUST be generated from an isolated input directory.
    use_inputs = [results_dir] if input_dirs is None else [p.expanduser().resolve() for p in input_dirs]
    for d in use_inputs:
        d.mkdir(parents=True, exist_ok=True)

    # BehaveX sanity check + flatten: BehaveX sometimes nests results under a subfolder (e.g. behavex/allure).
    # Move nested ``*-result.json`` files up into the root of the BehaveX results dir.
    for d in use_inputs:
        if d.name == "behavex":
            moved = _flatten_allure_result_json(root=d)
            if moved:
                print(f"[allure] flattened BehaveX results: moved {moved} *-result.json into {d}")

    def _count_results(p: Path) -> int:
        try:
            return len(list(p.rglob("*-result.json")))
        except OSError:
            return 0

    counts = {p.name: _count_results(p) for p in use_inputs}
    print("[allure] input counts: " + " ".join(f"{k}={v}" for k, v in counts.items()))
    if "behavex" in counts and counts["behavex"] == 0:
        print(f"[allure] WARNING: no BehaveX Allure result files found under {results_dir / 'behavex'}")

    report_dir.mkdir(parents=True, exist_ok=True)

    try:
        p = _invoke_allure_generate(
            result_dirs=use_inputs,
            report_dir=report_dir,
            single_file=True,
            subprocess_run=subprocess_run,
        )
    except FileNotFoundError:
        return False, "Allure Report 3 CLI not found. Run `npm install` in the repo root.", None
    except Exception as exc:
        from testo_core.reporting.allure_cli import AllureCLINotFoundError

        if isinstance(exc, AllureCLINotFoundError):
            return False, str(exc), None
        raise

    if p.returncode != 0:
        err = (p.stderr or p.stdout or "").strip()
        return False, f"Allure generation failed (exit {p.returncode}). {err[:2000]}", None

    publish_allure_index_to_static(report_dir=report_dir)
    health = compute_system_health_pct(results_dir)
    return True, f"Allure report generated at {report_dir}", health


def generate_allure_reports(
    *,
    results_dir: Path,
    frameworks: list[str] | None = None,
    subprocess_run: Callable[..., Any] | None = None,
) -> dict[str, tuple[bool, str, float | None]]:
    """
    Generate per-framework Allure HTML reports (strict isolation).

    Each framework is generated into its own directory:
      ``static/allure_reports/<framework>/index.html``

    Returns: mapping of ``framework_name`` → ``(ok, message, health_pct)``.
    """
    results_dir = results_dir.expanduser().resolve()
    out: dict[str, tuple[bool, str, float | None]] = {}

    if not frameworks:
        frameworks = ["pytest", "behavex", "behave_native"]

    def _pick_allure_inputs(framework_results_dir: Path) -> list[Path]:
        """
        Allure CLI builds may ignore nested JSON when only a parent dir is supplied.

        Our runners may scope results under: <framework>/<run_id>/...
        Prefer passing the run_id subfolders as explicit inputs when present.
        """
        framework_results_dir = framework_results_dir.expanduser().resolve()
        try:
            children = [p for p in framework_results_dir.iterdir() if p.is_dir()]
        except OSError:
            children = []

        if not children:
            return [framework_results_dir]

        picked: list[Path] = []
        for d in children:
            try:
                if any(d.rglob("*-result.json")):
                    picked.append(d)
            except OSError:
                continue
        return picked or [framework_results_dir]

    for fw in frameworks:
        fw_results = results_dir / fw
        fw_results.mkdir(parents=True, exist_ok=True)
        fw_out_dir = allure_report_dir(fw)
        fw_out_dir.mkdir(parents=True, exist_ok=True)

        input_dirs = _pick_allure_inputs(fw_results)
        # BehaveX flattening: results can be nested under the run folder too.
        if str(fw) == "behavex":
            for d in input_dirs:
                _flatten_allure_result_json(root=d)

        ok, msg, hp = generate_allure_html(
            results_dir=fw_results,
            report_dir=fw_out_dir,
            input_dirs=input_dirs,
            subprocess_run=subprocess_run,
        )
        out[str(fw)] = (ok, msg, hp)
    return out


def read_single_file_html(*, report_dir: Path) -> tuple[bool, str, bytes | None]:
    """
    Read the generated single-file Allure report (index.html).
    """
    report_dir = report_dir.expanduser().resolve()
    index = report_dir / "index.html"
    if not index.exists():
        return False, f"Missing {index}. Generate the report first.", None
    try:
        return True, "OK", index.read_bytes()
    except Exception as exc:
        return False, f"Failed reading {index}: {exc}", None


def make_report_zip(*, report_dir: Path, out_dir: Path, base_name: str = "allure-report") -> Path:
    """
    Create a zip archive of the Allure HTML report directory.
    Returns the full path to the generated zip file.
    """
    report_dir = report_dir.expanduser().resolve()
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    zip_base = out_dir / base_name
    zip_path = Path(shutil.make_archive(str(zip_base), "zip", root_dir=str(report_dir)))
    return zip_path


@dataclass
class ReportServer:
    port: int
    root_dir: Path
    thread: threading.Thread
    httpd: http.server.ThreadingHTTPServer

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    def stop(self) -> None:
        with contextlib.suppress(Exception):
            self.httpd.shutdown()
        with contextlib.suppress(Exception):
            self.httpd.server_close()


def start_report_server(*, report_dir: Path, port: int | None = None) -> ReportServer:
    """
    Start a local HTTP server rooted at the generated Allure report dir.
    This makes embedded viewing work (relative JS/CSS assets).
    """
    report_dir = report_dir.expanduser().resolve()
    if not report_dir.exists():
        raise FileNotFoundError(report_dir)

    chosen_port = port or _find_free_port()

    handler = _make_handler(report_dir)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", chosen_port), handler)

    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()

    return ReportServer(port=chosen_port, root_dir=report_dir, thread=t, httpd=httpd)


def start_static_server(*, root_dir: Path, port: int | None = None) -> ReportServer:
    """
    Serve a broader directory tree (e.g. orchestrator root), so we can open:
      - static/allure_report/index.html
      - static_reports/behavex/*.html
    """
    root_dir = root_dir.expanduser().resolve()
    if not root_dir.exists():
        raise FileNotFoundError(root_dir)
    chosen_port = port or _find_free_port()
    handler = _make_handler(root_dir)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", chosen_port), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return ReportServer(port=chosen_port, root_dir=root_dir, thread=t, httpd=httpd)


def _ensure_static_dirs() -> None:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)


def _chmod_tree(path: Path, *, dirmode: int = 0o755, filemode: int = 0o644) -> None:
    for root, dirs, files in os.walk(path):
        for name in files:
            fp = Path(root) / name
            try:
                os.chmod(fp, filemode)
            except OSError:
                pass
        for name in dirs:
            dp = Path(root) / name
            try:
                os.chmod(dp, dirmode)
            except OSError:
                pass
    try:
        os.chmod(path, dirmode)
    except OSError:
        pass


def _mirror_behavex_output_tree_to_static(src_dir: Path) -> Path | None:
    """
    Copy the full BehaveX output directory (HTML, ``outputs/``, assets) into ``static/behave/``,
    then copy ``report.html`` to ``index.html`` so Streamlit serves ``/app/static/behave/index.html``.
    """
    src_dir = src_dir.expanduser().resolve()
    report = src_dir / "report.html"
    if not src_dir.is_dir() or not report.is_file():
        return None

    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    if STATIC_BEHAVE_DIR.exists():
        shutil.rmtree(STATIC_BEHAVE_DIR)
    shutil.copytree(src_dir, STATIC_BEHAVE_DIR)
    shutil.copy2(STATIC_BEHAVE_DIR / "report.html", STATIC_BEHAVE_INDEX)
    _chmod_tree(STATIC_BEHAVE_DIR)
    try:
        os.chmod(STATIC_BEHAVE_INDEX, 0o644)
    except OSError:
        pass
    return STATIC_BEHAVE_INDEX if STATIC_BEHAVE_INDEX.is_file() else None


def _resolve_behavex_artifacts_output_dir(artifacts_root: Path) -> Path | None:
    """BehaveX ``-o`` directory under artifacts (prefers ``behave_reports``, then legacy ``behavex-output``)."""
    artifacts_root = artifacts_root.expanduser().resolve()
    for sub in ("behave_reports", "behavex-output"):
        d = artifacts_root / sub
        if d.is_dir() and (d / "report.html").is_file():
            return d
    return None


def _mirror_file_readable(src: Path, dst: Path) -> None:
    """Copy HTML into static/ and set permissive mode so Streamlit can serve it."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    try:
        os.chmod(dst, 0o644)
    except OSError:
        pass


def publish_allure_index_to_static(*, report_dir: Path) -> Path | None:
    """
    When ``report_dir`` is ``static/allure_report``, Allure already wrote ``index.html`` there;
    chmod the tree for Streamlit. Otherwise mirror ``index.html`` to legacy ``static/allure_report.html``.
    """
    report_dir = report_dir.expanduser().resolve()
    src = report_dir / "index.html"
    if not src.is_file():
        return None
    _ensure_static_dirs()
    # If report is already under the new static tree, just chmod.
    try:
        if STATIC_ALLURE_REPORTS_DIR.resolve() in report_dir.resolve().parents:
            _chmod_tree(report_dir)
            return src
    except Exception:
        pass
    if report_dir.resolve() == STATIC_ALLURE_REPORT_DIR.resolve():
        _chmod_tree(report_dir)
        return STATIC_ALLURE_INDEX if STATIC_ALLURE_INDEX.is_file() else src
    _mirror_file_readable(src, STATIC_ALLURE_HTML)
    return STATIC_ALLURE_HTML


def collect_behavex_native_report(
    *,
    target_repo: Path,
    run_id: str,
    artifacts_root: Path | None = None,
) -> Path | None:
    """
    BehaveX writes report.html at OUTPUT/report.html (see `-o`).

    Primary: <artifacts>/behave_reports/report.html
    Legacy:   <artifacts>/behavex-output/report.html, <target_repo>/output/report.html

    Mirrors the full BehaveX output dir to ``static/behave/`` (assets preserved), sets ``index.html``
    from ``report.html``, and copies ``report.html`` to ``static_reports/behavex/report_<run_id>.html``.
    """
    target_repo = target_repo.expanduser().resolve()
    candidates: list[Path] = []
    if artifacts_root is not None:
        ar = artifacts_root.expanduser().resolve()
        candidates.append(ar / "behave_reports" / "report.html")
        candidates.append(ar / "behavex-output" / "report.html")
    candidates.append(target_repo / "output" / "report.html")

    src: Path | None = None
    for c in candidates:
        if c.exists():
            src = c
            break
    if src is None:
        return None

    root = ORCHESTRATOR_ROOT
    mirrored = _mirror_behavex_output_tree_to_static(src.parent)
    if mirrored is None:
        return None

    dest_dir = (root / "static_reports" / "behavex").resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"report_{run_id}.html"
    _mirror_file_readable(src, dest)
    return dest


def sync_all_reports_to_static(*, artifacts_root: Path, run_id: str | None = None) -> dict[str, Path | None]:
    """
    Copy the latest known report HTML artifacts into ``./static/`` for Streamlit static serving.

    - Allure: any per-framework HTML under ``static/allure_reports/<framework>/index.html``
    - BehaveX: full ``<artifacts>/behave_reports/`` tree (legacy: ``behavex-output/``) → ``static/behave/``,
      with ``report.html`` copied to ``static/behave/index.html``
    """
    _ = run_id
    artifacts_root = artifacts_root.expanduser().resolve()
    out: dict[str, Path | None] = {"allure": None, "behavex": None}

    # Per-framework Allure HTML lives under ``static/allure_reports/``.
    if STATIC_ALLURE_REPORTS_DIR.is_dir():
        _ensure_static_dirs()
        _chmod_tree(STATIC_ALLURE_REPORTS_DIR)
        # Return one representative index so callers can print a stable path.
        for d in sorted([p for p in STATIC_ALLURE_REPORTS_DIR.iterdir() if p.is_dir()]):
            idx = d / "index.html"
            if idx.is_file():
                out["allure"] = idx
                break
    if out["allure"] is None and STATIC_ALLURE_INDEX.is_file():
        # Back-compat legacy path
        _ensure_static_dirs()
        _chmod_tree(STATIC_ALLURE_REPORT_DIR)
        out["allure"] = STATIC_ALLURE_INDEX
    if out["allure"] is None:
        # Back-compat artifacts → static single-file
        allure_index = artifacts_root / "allure-report" / "index.html"
        if allure_index.is_file():
            _ensure_static_dirs()
            _mirror_file_readable(allure_index, STATIC_ALLURE_HTML)
            out["allure"] = STATIC_ALLURE_HTML

    behave_dir = _resolve_behavex_artifacts_output_dir(artifacts_root)
    if behave_dir is not None:
        out["behavex"] = _mirror_behavex_output_tree_to_static(behave_dir)

    return out


def url_for(server: ReportServer, *, relative_path: str) -> str:
    rp = relative_path.lstrip("/")
    return f"{server.url}{rp}"

def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _make_handler(root_dir: Path):
    # python < 3.13 doesn't support passing directory via partial; do it explicitly
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root_dir), **kwargs)

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            # keep Streamlit logs clean
            return

    return Handler


def default_report_paths(*, artifacts_root: Path) -> ReportPaths:
    artifacts_root = artifacts_root.expanduser().resolve()
    results_dir = artifacts_root / "allure-results"
    report_dir = STATIC_ALLURE_REPORTS_DIR
    zip_path = artifacts_root / "allure-report.zip"
    return ReportPaths(results_dir=results_dir, report_dir=report_dir, zip_path=zip_path)

