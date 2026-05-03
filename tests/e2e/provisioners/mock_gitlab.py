from __future__ import annotations

from tests.e2e.flows.flow_scenario import FlowContext


class MockGitlabProvisioner:
    def provision(self, ctx: FlowContext) -> None:
        ctx.resources["gitlab_project"] = f"uqo-e2e-{ctx.run_id}-gitlab-mock"
        ctx.metadata["provider"] = "gitlab"

    def cleanup(self, ctx: FlowContext) -> None:
        ctx.resources.pop("gitlab_project", None)

