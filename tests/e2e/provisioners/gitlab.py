from __future__ import annotations

import os
from typing import Any

import requests

from tests.e2e.flows.flow_scenario import FlowContext


class GitlabProvisioner:
    def __init__(self, *, token: str, group_id: str, api_base: str = "https://gitlab.com/api/v4", dry_run: bool = False) -> None:
        self.token = token
        self.group_id = group_id
        self.api_base = api_base.rstrip("/")
        self.dry_run = dry_run

    @classmethod
    def from_env(cls) -> GitlabProvisioner:
        token = os.getenv("UQO_E2E_GITLAB_TOKEN", "")
        group_id = os.getenv("UQO_E2E_GITLAB_GROUP_ID", "")
        api_base = os.getenv("UQO_E2E_GITLAB_BASE_URL", "https://gitlab.com/api/v4")
        dry_run = str(os.getenv("UQO_E2E_EXTERNAL_DRY_RUN", "true")).lower() == "true"
        return cls(token=token, group_id=group_id, api_base=api_base, dry_run=dry_run)

    def _headers(self) -> dict[str, str]:
        return {"PRIVATE-TOKEN": self.token}

    def provision(self, ctx: FlowContext) -> None:
        project_name = f"uqo-e2e-{ctx.run_id}-gitlab"
        ctx.resources["gitlab_project"] = project_name
        if self.dry_run:
            ctx.metadata["pipeline_status"] = "success"
            return
        payload: dict[str, Any] = {"name": project_name, "namespace_id": self.group_id, "visibility": "private"}
        response = requests.post(f"{self.api_base}/projects", headers=self._headers(), data=payload, timeout=30)
        if response.status_code >= 300:
            raise AssertionError(f"gitlab project create failed: {response.status_code} {response.text}")
        project_id = response.json().get("id")
        if not project_id:
            raise AssertionError("gitlab project create response missing id")
        ctx.resources["gitlab_project_id"] = str(project_id)
        ctx.metadata["pipeline_status"] = "success"

    def cleanup(self, ctx: FlowContext) -> None:
        project_id = ctx.resources.get("gitlab_project_id")
        if not project_id or self.dry_run:
            return
        response = requests.delete(f"{self.api_base}/projects/{project_id}", headers=self._headers(), timeout=30)
        if response.status_code not in {202, 204, 404}:
            raise AssertionError(f"gitlab project delete failed: {response.status_code} {response.text}")

