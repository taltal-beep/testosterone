from __future__ import annotations

import pytest

from tests.e2e.flows.flow_runner import run_flow_scenario
from tests.e2e.flows.flow_scenario import FlowContext, FlowScenario
from tests.e2e.provisioners.mock_github import MockGithubProvisioner
from tests.e2e.provisioners.mock_gitlab import MockGitlabProvisioner

pytestmark = [pytest.mark.tier_heavy, pytest.mark.plugin_path]


class _Executor:
    def execute(self, ctx: FlowContext) -> None:
        ctx.metadata["plugin_loaded"] = True
        ctx.artifacts["plugin_log"] = "plugin execution completed"
        if ctx.metadata.get("simulate_plugin_failure"):
            raise RuntimeError("plugin execution failed")

    def poll(self, ctx: FlowContext) -> None:
        ctx.metadata["pipeline_status"] = "success"


class _PluginVerifier:
    def verify(self, ctx: FlowContext) -> None:
        if not ctx.metadata.get("plugin_loaded"):
            raise AssertionError("plugin did not load")
        if "plugin_log" not in ctx.artifacts:
            raise AssertionError("plugin artifact missing")


@pytest.mark.provider_github
def test_plugin_path_with_mocked_github_provider(cleanup_ledger, e2e_run_id: str) -> None:
    scenario = FlowScenario(
        name="plugin-github-mocked",
        provisioner=MockGithubProvisioner(),
        executor=_Executor(),
        verifiers=[_PluginVerifier()],
    )
    ctx = FlowContext(run_id=e2e_run_id, provider="github")

    result = run_flow_scenario(scenario, ctx, cleanup_ledger)

    assert result.status == "success"
    assert "github_repo" not in ctx.resources


@pytest.mark.provider_gitlab
def test_plugin_path_with_mocked_gitlab_provider(cleanup_ledger, e2e_run_id: str) -> None:
    scenario = FlowScenario(
        name="plugin-gitlab-mocked",
        provisioner=MockGitlabProvisioner(),
        executor=_Executor(),
        verifiers=[_PluginVerifier()],
    )
    ctx = FlowContext(run_id=e2e_run_id, provider="gitlab")

    result = run_flow_scenario(scenario, ctx, cleanup_ledger)

    assert result.status == "success"
    assert "gitlab_project" not in ctx.resources


@pytest.mark.provider_github
def test_plugin_failure_is_captured(cleanup_ledger, e2e_run_id: str) -> None:
    scenario = FlowScenario(
        name="plugin-failure-mocked",
        provisioner=MockGithubProvisioner(),
        executor=_Executor(),
        verifiers=[_PluginVerifier()],
    )
    ctx = FlowContext(run_id=e2e_run_id, provider="github", metadata={"simulate_plugin_failure": True})

    result = run_flow_scenario(scenario, ctx, cleanup_ledger)

    assert result.status == "failed"

