# Delta Comparison Policy

This document defines deterministic semantics for Phase 3 delta analytics.

## Run role semantics

- `baseline_run_id`: reference run used as the comparison anchor.
- `current_run_id`: run being evaluated against baseline.
- Delta formula:
  - `absolute_delta = current_value - baseline_value`
  - `relative_delta_pct = ((current_value - baseline_value) / baseline_value) * 100` when baseline is non-zero.

## Classification labels

- `improvement`: metric moved in a favorable direction.
- `regression`: metric moved in an unfavorable direction.
- `neutral`: no change (`absolute_delta == 0`).
- `unknown`: metric cannot be compared due to missing or incompatible data.

## Direction policy table

| Metric | Group | Better Direction | Notes |
| --- | --- | --- | --- |
| `total_tests` | reliability | higher | More executed tests means broader reliability signal. |
| `passed` | reliability | higher | More passing tests is better. |
| `failed` | reliability | lower | More failed tests is worse. |
| `broken` | reliability | lower | More broken tests is worse. |
| `skipped` | reliability | lower | More skipped tests is treated as worse coverage quality. |
| `health_pct` | reliability | higher | Higher health percentage is better. |
| `wall_duration_ms` | performance | lower | Lower wall-clock duration is better. |
| `metrics_duration_ms` | performance | lower | Lower aggregate metrics duration is better. |
| `avg_case_ms` | performance | lower | Lower average case duration is better. |

## Unknown/null reason codes

- `missing_current_metric`: current run has no value.
- `missing_baseline_metric`: baseline run has no value.
- `zero_baseline_for_relative`: absolute delta can be computed, relative percent cannot.
- `incompatible_test_kind`: run pair has different `test_kind`.

