from __future__ import annotations

from tests.conftest import CleanupLedger
from tests.e2e.flows.flow_scenario import FlowContext, FlowResult, FlowScenario


def run_flow_scenario(scenario: FlowScenario, ctx: FlowContext, ledger: CleanupLedger) -> FlowResult:
    """
    Canonical flow lifecycle: provision -> execute -> poll -> verify -> cleanup.
    Cleanup always runs and writes a ledger entry.
    """
    try:
        scenario.provisioner.provision(ctx)
        scenario.executor.execute(ctx)
        scenario.executor.poll(ctx)
        for verifier in scenario.verifiers:
            verifier.verify(ctx)
        return FlowResult(status="success")
    except Exception as exc:  # pragma: no cover - exercised in tests
        return FlowResult(status="failed", detail=str(exc))
    finally:
        try:
            scenario.provisioner.cleanup(ctx)
            ledger.add(
                resource_type="scenario",
                resource_id=scenario.name,
                provider=ctx.provider,
                status="cleaned",
            )
        except Exception as cleanup_exc:  # pragma: no cover - defensive logging path
            ledger.add(
                resource_type="scenario",
                resource_id=scenario.name,
                provider=ctx.provider,
                status="cleanup_failed",
                detail=str(cleanup_exc),
            )

