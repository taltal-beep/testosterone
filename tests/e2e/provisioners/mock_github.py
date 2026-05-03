from __future__ import annotations

from tests.e2e.flows.flow_scenario import FlowContext


class MockGithubProvisioner:
    def provision(self, ctx: FlowContext) -> None:
        ctx.resources["github_repo"] = f"uqo-e2e-{ctx.run_id}-github-mock"
        ctx.metadata["provider"] = "github"

    def cleanup(self, ctx: FlowContext) -> None:
        ctx.resources.pop("github_repo", None)

