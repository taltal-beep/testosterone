"""Walk a ``testo run`` artifacts tree and collect every Allure result dir.

The layout produced by :func:`testo_core.engine.orchestrator.run_plan` is:

```
<artifacts_root>/
  <plan>/
    events.ndjson
    plan_result.json
    <stage>/
      run.log
      allure-results/
        <framework>/
          *-result.json
```

The collector is **read-only** — Allure / JUnit exporters consume the
returned :class:`CollectedResults` and decide whether to copy, generate, or
stream from each entry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from testo_core.reporting.paths import discover_plan_dirs, plan_artifacts_dir


@dataclass(frozen=True)
class StageCollection:
    """One stage's raw artifacts."""

    plan: str
    stage: str
    framework: str
    results_dir: Path
    log_path: Path | None


@dataclass(frozen=True)
class CollectedResults:
    """A flat list of per-framework Allure result trees discovered on disk."""

    artifacts_root: Path
    stages: list[StageCollection] = field(default_factory=list)

    @property
    def result_dirs(self) -> list[Path]:
        return [s.results_dir for s in self.stages if s.results_dir.is_dir()]

    @property
    def by_framework(self) -> dict[str, list[Path]]:
        out: dict[str, list[Path]] = {}
        for s in self.stages:
            out.setdefault(s.framework, []).append(s.results_dir)
        return out


def collect_results(
    artifacts_root: Path,
    *,
    plan_name: str | None = None,
) -> CollectedResults:
    """Discover every per-stage Allure result directory on disk."""
    artifacts_root = artifacts_root.expanduser().resolve()
    plan_dirs: list[Path]
    if plan_name is not None:
        plan_dir = plan_artifacts_dir(artifacts_root, plan_name)
        plan_dirs = [plan_dir] if plan_dir.is_dir() else []
    else:
        plan_dirs = discover_plan_dirs(artifacts_root)

    stages: list[StageCollection] = []
    for plan_dir in plan_dirs:
        plan_label = plan_dir.name
        for stage_dir in sorted(p for p in plan_dir.iterdir() if p.is_dir()):
            allure_root = stage_dir / "allure-results"
            if not allure_root.is_dir():
                continue
            log_path = stage_dir / "run.log"
            for framework_dir in sorted(p for p in allure_root.iterdir() if p.is_dir()):
                stages.append(
                    StageCollection(
                        plan=plan_label,
                        stage=stage_dir.name,
                        framework=framework_dir.name,
                        results_dir=framework_dir,
                        log_path=log_path if log_path.is_file() else None,
                    )
                )
    return CollectedResults(artifacts_root=artifacts_root, stages=stages)
