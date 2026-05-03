from __future__ import annotations

from tests.e2e.flows.flow_scenario import FlowContext


class ProviderStatusVerifier:
    def verify(self, ctx: FlowContext) -> None:
        status = ctx.metadata.get("pipeline_status")
        if status not in {"success", "passed"}:
            raise AssertionError(f"provider pipeline/action did not succeed: {status}")

