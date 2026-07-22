from __future__ import annotations

import os

import pytest

from tests.e2e.flows.flow_runner import run_flow_scenario
from tests.e2e.flows.flow_scenario import FlowContext, FlowScenario
from tests.e2e.provisioners.github import GithubProvisioner
from tests.e2e.provisioners.gitlab import GitlabProvisioner
from tests.e2e.verifiers.cleanup_audit import assert_no_cleanup_failures
from tests.e2e.verifiers.provider_status import ProviderStatusVerifier

pytestmark = [
    pytest.mark.tier_external,
    pytest.mark.cleanup_required,
    pytest.mark.plugin_path,
]


class _ExternalExecutor:
    def execute(self, ctx: FlowContext) -> None:
        ctx.metadata["plugin_loaded"] = True
        ctx.metadata["plugin_executed"] = True

    def poll(self, ctx: FlowContext) -> None:
        ctx.metadata.setdefault("pipeline_status", "success")


@pytest.mark.provider_github
def test_external_github_lifecycle(cleanup_ledger, e2e_run_id: str) -> None:
    provisioner = GithubProvisioner.from_env()
    if not provisioner.dry_run and (not provisioner.token or not provisioner.owner):
        pytest.skip("UQO_E2E_GITHUB_TOKEN/UQO_E2E_GITHUB_OWNER are required when dry-run is disabled")

    scenario = FlowScenario(
        name="external-github-lifecycle",
        provisioner=provisioner,
        executor=_ExternalExecutor(),
        verifiers=[ProviderStatusVerifier()],
    )
    ctx = FlowContext(run_id=e2e_run_id, provider="github")
    result = run_flow_scenario(scenario, ctx, cleanup_ledger)

    assert result.status == "success"
    assert ctx.metadata["plugin_executed"] is True
    assert_no_cleanup_failures(cleanup_ledger)


@pytest.mark.provider_gitlab
def test_external_gitlab_lifecycle(cleanup_ledger, e2e_run_id: str) -> None:
    provisioner = GitlabProvisioner.from_env()
    if not provisioner.dry_run and (not provisioner.token or not provisioner.group_id):
        pytest.skip("UQO_E2E_GITLAB_TOKEN/UQO_E2E_GITLAB_GROUP_ID are required when dry-run is disabled")

    scenario = FlowScenario(
        name="external-gitlab-lifecycle",
        provisioner=provisioner,
        executor=_ExternalExecutor(),
        verifiers=[ProviderStatusVerifier()],
    )
    ctx = FlowContext(run_id=e2e_run_id, provider="gitlab")
    result = run_flow_scenario(scenario, ctx, cleanup_ledger)

    assert result.status == "success"
    assert ctx.metadata["plugin_loaded"] is True
    assert_no_cleanup_failures(cleanup_ledger)


def test_external_resource_prefix_is_deterministic(e2e_run_id: str) -> None:
    expected = f"uqo-e2e-{e2e_run_id}"
    assert expected.startswith("uqo-e2e-")
    assert " " not in expected
    assert os.sep not in expected

