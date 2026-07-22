"""Pre-serve mutations on current Allure ``*-result.json`` for delta-first reporting."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from testo_core.services.report_archive_diff import (
    _case_group,
    _load_cases,
    allure_case_key,
    case_synopsis_from_result,
    classify_case_change,
)


def _label_value(labels: Any, name: str) -> str:
    if not isinstance(labels, list):
        return ""
    for lab in labels:
        if isinstance(lab, dict) and str(lab.get("name")) == name:
            v = lab.get("value")
            return str(v).strip() if v is not None else ""
    return ""


def _suite_display_key(data: dict[str, Any]) -> str:
    labels = data.get("labels") or []
    ps = _label_value(labels, "parentSuite")
    if ps:
        return ps[:200]
    su = _label_value(labels, "suite")
    if su:
        return su[:200]
    pkg = _label_value(labels, "package")
    if pkg:
        return pkg[:200]
    return _case_group(data)


def _primary_label_name_for_suffix(data: dict[str, Any]) -> str | None:
    labels = data.get("labels")
    if not isinstance(labels, list):
        return None
    for name in ("parentSuite", "suite", "package"):
        if _label_value(labels, name):
            return name
    return None


def _suite_pass_rates(plan_root: Path) -> dict[str, tuple[int, int]]:
    """Map suite display key -> (passed_count, total_count)."""

    counts: dict[str, tuple[int, int]] = {}
    if not plan_root.is_dir():
        return counts
    for path in plan_root.rglob("*-result.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        key = _suite_display_key(data)
        st = str(data.get("status") or "unknown").lower()
        p, t = counts.get(key, (0, 0))
        t += 1
        if st == "passed":
            p += 1
        counts[key] = (p, t)
    return counts


def _delta_pp(base: dict[str, tuple[int, int]], cur: dict[str, tuple[int, int]], suite_key: str) -> float | None:
    bp, bt = base.get(suite_key, (0, 0))
    cp, ct = cur.get(suite_key, (0, 0))
    if bt <= 0 or ct <= 0:
        return None
    return 100.0 * (cp / ct) - 100.0 * (bp / bt)


def _format_suite_delta(delta_pp: float | None, *, use_emoji: bool) -> str:
    if delta_pp is None:
        return ""
    text = f"{delta_pp:+.1f}%"
    if use_emoji:
        if delta_pp > 0.0001:
            return f" ({text} 📈)"
        if delta_pp < -0.0001:
            return f" ({text} 📉)"
    return f" ({text})"


_MARK_RE = re.compile(r"\[TESTO:(REGRESSION|FIXED|NEW_FAILURE|PERSISTENT|STATUS_CHANGE)\]")


def _prefix_status_message(data: dict[str, Any], token: str) -> None:
    sd = data.get("statusDetails")
    if not isinstance(sd, dict):
        sd = {}
    msg = sd.get("message", "")
    if not isinstance(msg, str):
        msg = str(msg) if msg is not None else ""
    if token in msg:
        return
    # Strip prior TESTO markers so re-runs stay clean
    msg = _MARK_RE.sub("", msg).strip()
    sd["message"] = f"{token} {msg}".strip() if msg else token
    data["statusDetails"] = sd


def _append_suite_suffix(data: dict[str, Any], suffix: str, label_name: str) -> None:
    if not suffix:
        return
    labels = data.get("labels")
    if not isinstance(labels, list):
        return
    for lab in labels:
        if isinstance(lab, dict) and str(lab.get("name")) == label_name:
            val = lab.get("value")
            if not isinstance(val, str):
                val = str(val) if val is not None else ""
            if suffix.strip() in val or re.search(r"\([+-]\d+\.\d+%", val):
                return
            lab["value"] = f"{val}{suffix}"
            return


def _append_label(data: dict[str, Any], name: str, value: str) -> None:
    labels = data.get("labels")
    if not isinstance(labels, list):
        labels = []
        data["labels"] = labels
    for lab in labels:
        if isinstance(lab, dict) and str(lab.get("name")) == name and str(lab.get("value")) == value:
            return
    labels.append({"name": name, "value": value})


@dataclass(frozen=True)
class DeltaMutationStats:
    """Summary text for ``environment.properties`` and sidecars."""

    performance_summary_md: str


def _perf_row(name: str, delta_ms: int) -> str:
    safe = name.replace("|", "\\|")
    return f"| {safe} | +{delta_ms} ms |"


def apply_delta_first_mutations(
    *,
    baseline_plan_root: Path,
    current_plan_root: Path,
) -> DeltaMutationStats:
    """Rewrite current plan ``*-result.json`` in place for categories, suite deltas, and tags."""

    baseline_cases = _load_cases(baseline_plan_root)
    base_rates = _suite_pass_rates(baseline_plan_root)
    cur_rates = _suite_pass_rates(current_plan_root)
    use_emoji = os.environ.get("TESTO_ALLURE_DELTA_EMOJI", "").strip().lower() in {"1", "true", "yes"}

    perf_candidates: list[tuple[str, int]] = []

    if not current_plan_root.is_dir():
        return DeltaMutationStats(performance_summary_md="")

    for path in sorted(current_plan_root.rglob("*-result.json")):
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict):
            continue

        b = baseline_cases.get(allure_case_key(data))
        c_syn = case_synopsis_from_result(data)
        kind = classify_case_change(b, c_syn)
        cs = c_syn["status"]

        bd = (b or {}).get("duration_ms") if b else None
        cd = c_syn.get("duration_ms")
        if isinstance(bd, int) and isinstance(cd, int) and cd > bd:
            name = str(data.get("name") or data.get("fullName") or allure_case_key(data))[:120]
            perf_candidates.append((name, cd - bd))

        # Suite pass-rate suffix on primary suite label
        sk = _suite_display_key(data)
        dpp = _delta_pp(base_rates, cur_rates, sk)
        lbl = _primary_label_name_for_suffix(data)
        if lbl and dpp is not None:
            _append_suite_suffix(data, _format_suite_delta(dpp, use_emoji=use_emoji), lbl)

        # Markers + tags + severity
        if kind == "regression":
            _prefix_status_message(data, "[TESTO:REGRESSION]")
            data["severity"] = "blocker"
            _append_label(data, "tag", "REGRESSION")
        elif kind == "fix":
            _prefix_status_message(data, "[TESTO:FIXED]")
        elif kind == "added" and cs in {"failed", "broken"}:
            _prefix_status_message(data, "[TESTO:NEW_FAILURE]")
        elif (
            kind == "unchanged"
            and b is not None
            and b["status"] in {"failed", "broken"}
            and cs in {"failed", "broken"}
        ):
            _prefix_status_message(data, "[TESTO:PERSISTENT]")
        elif kind == "status_change":
            _prefix_status_message(data, "[TESTO:STATUS_CHANGE]")

        try:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError:
            continue

    perf_candidates.sort(key=lambda x: -x[1])
    top = perf_candidates[:5]
    if not top:
        return DeltaMutationStats(performance_summary_md="")

    lines = [
        "| Test (slowdown) | Δ duration |",
        "| --- | --- |",
        *[_perf_row(n, d) for n, d in top],
    ]
    return DeltaMutationStats(performance_summary_md="\n".join(lines))
