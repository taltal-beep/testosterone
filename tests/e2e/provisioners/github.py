from __future__ import annotations

import os
from typing import Any

import requests

from tests.e2e.flows.flow_scenario import FlowContext


class GithubProvisioner:
    def __init__(self, *, token: str, owner: str, api_base: str = "https://api.github.com", dry_run: bool = False) -> None:
        self.token = token
        self.owner = owner
        self.api_base = api_base.rstrip("/")
        self.dry_run = dry_run

    @classmethod
    def from_env(cls) -> GithubProvisioner:
        token = os.getenv("UQO_E2E_GITHUB_TOKEN", "")
        owner = os.getenv("UQO_E2E_GITHUB_OWNER", "")
        dry_run = str(os.getenv("UQO_E2E_EXTERNAL_DRY_RUN", "true")).lower() == "true"
        return cls(token=token, owner=owner, dry_run=dry_run)

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def provision(self, ctx: FlowContext) -> None:
        repo_name = f"uqo-e2e-{ctx.run_id}-github"
        ctx.resources["github_repo"] = repo_name
        if self.dry_run:
            ctx.metadata["pipeline_status"] = "success"
            return
        payload: dict[str, Any] = {"name": repo_name, "private": True, "auto_init": True}
        response = requests.post(f"{self.api_base}/orgs/{self.owner}/repos", headers=self._headers(), json=payload, timeout=30)
        if response.status_code >= 300:
            raise AssertionError(f"github repo create failed: {response.status_code} {response.text}")
        ctx.metadata["pipeline_status"] = "success"

    def cleanup(self, ctx: FlowContext) -> None:
        repo_name = ctx.resources.get("github_repo")
        if not repo_name or self.dry_run:
            return
        response = requests.delete(f"{self.api_base}/repos/{self.owner}/{repo_name}", headers=self._headers(), timeout=30)
        if response.status_code not in {204, 404}:
            raise AssertionError(f"github repo delete failed: {response.status_code} {response.text}")

