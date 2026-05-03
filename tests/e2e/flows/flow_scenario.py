from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class FlowContext:
    run_id: str
    provider: str
    metadata: dict[str, Any] = field(default_factory=dict)
    resources: dict[str, str] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)


@dataclass
class FlowResult:
    status: str
    detail: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


class Provisioner(Protocol):
    def provision(self, ctx: FlowContext) -> None: ...
    def cleanup(self, ctx: FlowContext) -> None: ...


class Executor(Protocol):
    def execute(self, ctx: FlowContext) -> None: ...
    def poll(self, ctx: FlowContext) -> None: ...


class Verifier(Protocol):
    def verify(self, ctx: FlowContext) -> None: ...


@dataclass
class FlowScenario:
    name: str
    provisioner: Provisioner
    executor: Executor
    verifiers: list[Verifier]

