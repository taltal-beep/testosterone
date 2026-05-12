from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class CIProvenance:
    ci_provider: str
    ci_pipeline_id: str | None = None
    ci_job_id: str | None = None
    ci_commit_sha: str | None = None
    ci_ref_name: str | None = None

    def to_metadata(self) -> dict[str, str]:
        payload: dict[str, str] = {"ci_provider": self.ci_provider}
        if self.ci_pipeline_id:
            payload["ci_pipeline_id"] = self.ci_pipeline_id
        if self.ci_job_id:
            payload["ci_job_id"] = self.ci_job_id
        if self.ci_commit_sha:
            payload["ci_commit_sha"] = self.ci_commit_sha
        if self.ci_ref_name:
            payload["ci_ref_name"] = self.ci_ref_name
        return payload


def detect_ci_provenance(env: Mapping[str, str] | None = None) -> CIProvenance | None:
    source = env or {}
    if str(source.get("GITHUB_ACTIONS", "")).lower() == "true":
        return CIProvenance(
            ci_provider="github",
            ci_pipeline_id=source.get("GITHUB_RUN_ID"),
            ci_job_id=source.get("GITHUB_JOB"),
            ci_commit_sha=source.get("GITHUB_SHA"),
            ci_ref_name=source.get("GITHUB_REF_NAME"),
        )
    if str(source.get("GITLAB_CI", "")).lower() == "true":
        return CIProvenance(
            ci_provider="gitlab",
            ci_pipeline_id=source.get("CI_PIPELINE_ID"),
            ci_job_id=source.get("CI_JOB_ID"),
            ci_commit_sha=source.get("CI_COMMIT_SHA"),
            ci_ref_name=source.get("CI_COMMIT_REF_NAME"),
        )
    if str(source.get("BUILDKITE", "")).lower() == "true":
        return CIProvenance(
            ci_provider="buildkite",
            ci_pipeline_id=source.get("BUILDKITE_BUILD_ID"),
            ci_job_id=source.get("BUILDKITE_JOB_ID"),
            ci_commit_sha=source.get("BUILDKITE_COMMIT"),
            ci_ref_name=source.get("BUILDKITE_BRANCH"),
        )
    if str(source.get("CIRCLECI", "")).lower() == "true":
        return CIProvenance(
            ci_provider="circleci",
            ci_pipeline_id=source.get("CIRCLE_WORKFLOW_ID"),
            ci_job_id=source.get("CIRCLE_BUILD_NUM"),
            ci_commit_sha=source.get("CIRCLE_SHA1"),
            ci_ref_name=source.get("CIRCLE_BRANCH"),
        )
    if source.get("JENKINS_URL"):
        return CIProvenance(
            ci_provider="jenkins",
            ci_pipeline_id=source.get("BUILD_TAG") or source.get("BUILD_ID"),
            ci_job_id=source.get("BUILD_NUMBER"),
            ci_commit_sha=source.get("GIT_COMMIT"),
            ci_ref_name=source.get("GIT_BRANCH") or source.get("BRANCH_NAME"),
        )
    if source.get("TF_BUILD") == "True" or source.get("TF_BUILD") == "true":
        return CIProvenance(
            ci_provider="azure_pipelines",
            ci_pipeline_id=source.get("BUILD_BUILDID"),
            ci_job_id=source.get("SYSTEM_JOBID"),
            ci_commit_sha=source.get("BUILD_SOURCEVERSION"),
            ci_ref_name=source.get("BUILD_SOURCEBRANCHNAME"),
        )
    if str(source.get("CI", "")).lower() == "true":
        return CIProvenance(ci_provider="generic")
    return None


def detect_ci_environment(env: Mapping[str, str] | None = None) -> bool:
    return detect_ci_provenance(env) is not None
