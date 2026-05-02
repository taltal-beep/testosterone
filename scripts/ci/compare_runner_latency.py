from __future__ import annotations

import argparse
import json
from pathlib import Path


def _read_payload(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return {str(k): float(v) for k, v in payload.items() if isinstance(v, int | float)}


def _value(payload: dict[str, float], *candidates: str) -> float:
    for key in candidates:
        if key in payload:
            return float(payload[key])
    raise ValueError(f"Missing required metrics key. Tried: {', '.join(candidates)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare legacy vs runner-image latency metrics.")
    parser.add_argument("--baseline", required=True, type=Path, help="Legacy path metrics JSON.")
    parser.add_argument("--candidate", required=True, type=Path, help="Image path metrics JSON.")
    parser.add_argument("--max-startup-regression", type=float, default=0.0)
    parser.add_argument("--min-e2e-improvement-pct", type=float, default=20.0)
    args = parser.parse_args(argv)

    baseline = _read_payload(args.baseline)
    candidate = _read_payload(args.candidate)

    baseline_startup = _value(baseline, "startup_latency_s", "startup_s")
    candidate_startup = _value(candidate, "startup_latency_s", "startup_s")
    baseline_total = _value(baseline, "duration_s", "e2e_duration_s")
    candidate_total = _value(candidate, "duration_s", "e2e_duration_s")

    startup_delta = candidate_startup - baseline_startup
    improvement_pct = ((baseline_total - candidate_total) / baseline_total) * 100.0

    if startup_delta > float(args.max_startup_regression):
        raise SystemExit(
            f"Startup regression too high: {startup_delta:.3f}s > {args.max_startup_regression:.3f}s"
        )
    if improvement_pct < float(args.min_e2e_improvement_pct):
        raise SystemExit(
            f"E2E improvement too low: {improvement_pct:.2f}% < {args.min_e2e_improvement_pct:.2f}%"
        )

    print(
        json.dumps(
            {
                "startup_delta_s": round(startup_delta, 3),
                "e2e_improvement_pct": round(improvement_pct, 2),
            },
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
