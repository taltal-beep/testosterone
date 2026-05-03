from __future__ import annotations

from tests.e2e.flows.flow_scenario import FlowContext


class LocalProvisioner:
    def provision(self, ctx: FlowContext) -> None:
        ctx.resources["workspace"] = f"local-{ctx.run_id}"

    def cleanup(self, ctx: FlowContext) -> None:
        ctx.resources.pop("workspace", None)

