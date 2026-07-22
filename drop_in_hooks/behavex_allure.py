"""
BehaveX 4.x custom formatter bridge: maps merged BehaveX JSON to Allure result files.

BehaveX calls `FormatterClass()` with no arguments and then `launch_json_formatter(json_output)`.
The standard `allure_behave.formatter:AllureFormatter` is incompatible with that contract, which
causes: AllureFormatter.__init__() missing 2 required positional arguments.
"""

from __future__ import annotations

import json
import os
import traceback
import uuid
from pathlib import Path
from typing import Any

from allure_commons.model2 import Label, Status, StatusDetails, TestResult, TestStepResult
from attr import asdict


def _map_status(raw: str | None) -> str:
    s = (raw or "").lower()
    if s == "passed":
        return Status.PASSED
    if s == "failed":
        return Status.FAILED
    if s in ("error", "undefined"):
        return Status.BROKEN
    if s in ("skipped", "untested"):
        return Status.SKIPPED
    return Status.UNKNOWN


def _step_to_result(step: dict[str, Any], idx: int) -> TestStepResult:
    title = step.get("text") or step.get("name") or f"step_{idx}"
    st = _map_status(step.get("status"))
    details = None
    if st in (Status.FAILED, Status.BROKEN):
        msg_parts = []
        em = step.get("error_msg")
        if em:
            msg_parts.append(str(em))
        el = step.get("error_lines")
        if isinstance(el, list):
            msg_parts.extend(str(x) for x in el)
        msg = "\n".join(msg_parts).strip()
        if msg:
            details = StatusDetails(message=msg[:8000])
    return TestStepResult(
        name=str(title)[:2000],
        status=st,
        statusDetails=details,
    )


def _write_test_result(out_dir: Path, result: TestResult) -> None:
    fn = result.file_pattern.format(prefix=uuid.uuid4())
    data = asdict(result, filter=lambda _, v: v or v is False)
    path = out_dir / fn
    with open(path, "w", encoding="utf8") as f:
        json.dump(data, f, ensure_ascii=False)


class BehavexAllureExporter:
    """
    Declares a preferred subfolder name under the BehaveX output dir (informational).
    Actual Allure JSON is written to UQO_SHARED_ALLURE_RESULTS_DIR.
    """

    DEFAULT_OUTPUT_DIR = "allure-results"

    def launch_json_formatter(self, json_output: dict[str, Any]) -> None:
        raw_dir = os.environ.get("UQO_SHARED_ALLURE_RESULTS_DIR")
        if not raw_dir:
            print("[BehavexAllureExporter] UQO_SHARED_ALLURE_RESULTS_DIR is not set; skipping Allure export.")
            return

        out_dir = Path(raw_dir).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        features = json_output.get("features") or []
        try:
            for feature in features:
                feature_name = str(feature.get("name") or "Feature")
                feature_file = str(feature.get("filename") or "")
                for scenario in feature.get("scenarios") or []:
                    self._emit_scenario(out_dir, feature_name, feature_file, scenario)
        except Exception:
            print("[BehavexAllureExporter] Failed to export Allure results:")
            traceback.print_exc()

        # BehaveX skips the stock HTML report when `-f` is set; regenerate native report.html
        # so `static/behave/index.html` and HTTP viewers keep working.
        try:
            from behavex.outputs import report_html as behavex_report_html

            behavex_report_html.generate_report(json_output)
        except Exception:
            print("[BehavexAllureExporter] Native BehaveX HTML report generation failed:")
            traceback.print_exc()

    def _emit_scenario(self, out_dir: Path, feature_name: str, feature_file: str, scenario: dict[str, Any]) -> None:
        name = str(scenario.get("name") or "scenario")
        full_name = f"{feature_file}::{name}" if feature_file else name
        st = _map_status(scenario.get("status"))
        details = None
        if st in (Status.FAILED, Status.BROKEN):
            msg_parts = []
            em = scenario.get("error_msg")
            if isinstance(em, list):
                msg_parts.extend(str(x) for x in em)
            elif em:
                msg_parts.append(str(em))
            el = scenario.get("error_lines")
            if isinstance(el, list):
                msg_parts.extend(str(x) for x in el)
            msg = "\n".join(msg_parts).strip()
            if msg:
                details = StatusDetails(message=msg[:8000])

        steps_out: list[TestStepResult] = []
        bg = scenario.get("background")
        if isinstance(bg, dict):
            for bs in bg.get("steps") or []:
                steps_out.append(_step_to_result(bs, len(steps_out)))

        for idx, step in enumerate(scenario.get("steps") or []):
            steps_out.append(_step_to_result(step, idx))

        labels = [
            Label(name="feature", value=feature_name[:255]),
            Label(name="suite", value=feature_file[:255] if feature_file else feature_name[:255]),
        ]

        hist = scenario.get("identifier_hash") or scenario.get("id_hash") or full_name

        result = TestResult(
            uuid=str(uuid.uuid4()),
            name=name,
            fullName=full_name[:2000],
            historyId=str(hist)[:500],
            status=st,
            statusDetails=details,
            labels=labels,
            steps=steps_out,
        )
        _write_test_result(out_dir, result)
