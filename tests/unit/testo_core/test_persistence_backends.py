"""Unit tests for testo_core.persistence backends (Sprint 3 — Task 3.1.7)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from testo_core.engine.exit_codes import EngineExitCode
from testo_core.engine.result import PlanResult, StageResult
from testo_core.persistence.backend import PersistenceBackend
from testo_core.persistence.composite import composite_backend
from testo_core.persistence.db_backend import DbBackend
from testo_core.persistence.json_backend import JsonBackend


def _make_plan_result(
    plan_name: str = "smoke",
    exit_code: EngineExitCode = EngineExitCode.SUCCESS,
    artifacts_dir: Path = Path("artifacts/smoke"),
) -> PlanResult:
    stage = StageResult(
        stage_name="api",
        framework="pytest",
        returncode=0 if exit_code == EngineExitCode.SUCCESS else 1,
        started_at=1000.0,
        finished_at=1002.5,
        duration_s=2.5,
        log_path=Path("artifacts/smoke/api.log"),
        artifacts_dir=artifacts_dir,
        command=("pytest", "-q"),
        output_tail="1 passed",
        timed_out=False,
    )
    return PlanResult(
        plan_name=plan_name,
        started_at=1000.0,
        finished_at=1002.5,
        duration_s=2.5,
        stages=(stage,),
        aggregate_returncode=stage.returncode,
        exit_code=exit_code,
    )


def _write_allure_result(results_dir: Path, name: str, status: str) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    payload = {"name": name, "fullName": name, "status": status, "start": 0, "stop": 1}
    (results_dir / f"{name}-result.json").write_text(json.dumps(payload), encoding="utf-8")


class TestJsonBackend:
    def test_satisfies_protocol(self) -> None:
        backend = JsonBackend(Path("/tmp"))
        assert isinstance(backend, PersistenceBackend)

    def test_writes_plan_result_json(self, tmp_path: Path) -> None:
        backend = JsonBackend(tmp_path)
        result = _make_plan_result()
        backend.persist(result)

        out = tmp_path / "smoke" / "plan_result.json"
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["plan"] == "smoke"
        assert data["exit_code"] == 0
        assert len(data["stages"]) == 1
        assert data["stages"][0]["name"] == "api"

    def test_writes_failure_exit_code(self, tmp_path: Path) -> None:
        backend = JsonBackend(tmp_path)
        result = _make_plan_result(exit_code=EngineExitCode.DOMAIN_FAILURE)
        backend.persist(result)

        data = json.loads((tmp_path / "smoke" / "plan_result.json").read_text())
        assert data["exit_code"] == 1
        assert data["stages"][0]["returncode"] == 1

    def test_silently_handles_write_error(self, tmp_path: Path) -> None:
        backend = JsonBackend(Path("/nonexistent/deeply/nested/path"))
        result = _make_plan_result()
        backend.persist(result)

    def test_health_pct_is_real_pass_rate_not_binary_returncode(self, tmp_path: Path) -> None:
        """A stage subprocess can exit non-zero (one test failed) while most
        tests in it passed — health_pct must reflect the real pass rate
        (2/3 = 66.67%), not the binary 0% a returncode-only estimate gives."""
        stage_dir = tmp_path / "stage" / "api"
        results_dir = stage_dir / "allure-results" / "pytest"
        _write_allure_result(results_dir, "test_one", "passed")
        _write_allure_result(results_dir, "test_two", "passed")
        _write_allure_result(results_dir, "test_three", "failed")

        backend = JsonBackend(tmp_path)
        result = _make_plan_result(exit_code=EngineExitCode.DOMAIN_FAILURE, artifacts_dir=stage_dir)
        backend.persist(result)

        data = json.loads((tmp_path / "smoke" / "plan_result.json").read_text())
        stage = data["stages"][0]
        assert stage["total_tests"] == 3
        assert stage["passed"] == 2
        assert stage["failed"] == 1
        assert stage["health_pct"] == pytest.approx(66.666, abs=0.01)
        assert data["health_pct"] == pytest.approx(66.666, abs=0.01)
        assert data["total_tests"] == 3
        assert data["passed"] == 2

    def test_health_pct_falls_back_to_binary_estimate_when_no_allure_results(self, tmp_path: Path) -> None:
        backend = JsonBackend(tmp_path)
        result = _make_plan_result(exit_code=EngineExitCode.DOMAIN_FAILURE)
        backend.persist(result)

        data = json.loads((tmp_path / "smoke" / "plan_result.json").read_text())
        assert data["stages"][0]["total_tests"] == 0
        assert data["health_pct"] == 0.0


class TestDbBackend:
    def test_satisfies_protocol(self, tmp_path: Path) -> None:
        backend = DbBackend(tmp_path)
        assert isinstance(backend, PersistenceBackend)

    @patch("testo_core.db.get_repository")
    def test_persists_successful_run(self, mock_get_repo: MagicMock, tmp_path: Path) -> None:
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        backend = DbBackend(tmp_path)
        result = _make_plan_result()
        backend.persist(result)

        mock_repo.create_run.assert_called_once()
        call_kwargs = mock_repo.create_run.call_args[1]
        assert call_kwargs["status"].value == "COMPLETED"
        assert call_kwargs["metadata"]["plan"] == "smoke"
        assert call_kwargs["metadata"]["source"] == "engine"

    @patch("testo_core.db.get_repository")
    def test_health_pct_is_real_pass_rate_not_binary_returncode(self, mock_get_repo: MagicMock, tmp_path: Path) -> None:
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        stage_dir = tmp_path / "stage" / "api"
        results_dir = stage_dir / "allure-results" / "pytest"
        _write_allure_result(results_dir, "test_one", "passed")
        _write_allure_result(results_dir, "test_two", "passed")
        _write_allure_result(results_dir, "test_three", "failed")

        backend = DbBackend(tmp_path)
        result = _make_plan_result(exit_code=EngineExitCode.DOMAIN_FAILURE, artifacts_dir=stage_dir)
        backend.persist(result)

        metadata = mock_repo.create_run.call_args[1]["metadata"]
        stage = metadata["stages"][0]
        assert stage["total_tests"] == 3
        assert stage["passed"] == 2
        assert stage["health_pct"] == pytest.approx(66.666, abs=0.01)
        assert metadata["health_pct"] == pytest.approx(66.666, abs=0.01)

    @patch("testo_core.db.get_repository")
    def test_persists_failed_run(self, mock_get_repo: MagicMock, tmp_path: Path) -> None:
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        backend = DbBackend(tmp_path)
        result = _make_plan_result(exit_code=EngineExitCode.DOMAIN_FAILURE)
        backend.persist(result)

        call_kwargs = mock_repo.create_run.call_args[1]
        assert call_kwargs["status"].value == "FAILED"

    @patch("testo_core.db.get_repository", side_effect=Exception("no db"))
    def test_silently_handles_db_error(self, _mock: MagicMock, tmp_path: Path) -> None:
        backend = DbBackend(tmp_path)
        result = _make_plan_result()
        run_id = backend.persist(result)
        assert run_id is None

    @patch("testo_core.db.get_repository")
    def test_returns_persisted_run_id_on_success(self, mock_get_repo: MagicMock, tmp_path: Path) -> None:
        mock_repo = MagicMock()
        fake_record = MagicMock()
        fake_record.id = "abc-123"
        mock_repo.create_run.return_value = fake_record
        mock_get_repo.return_value = mock_repo

        backend = DbBackend(tmp_path)
        result = _make_plan_result()
        run_id = backend.persist(result)

        assert run_id == "abc-123"

    @patch("testo_core.db.get_repository")
    def test_sets_local_snapshot_dir_under_orchestrator_root(self, mock_get_repo: MagicMock) -> None:
        from testo_core.persistence.db_backend import ORCHESTRATOR_ROOT

        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        artifacts_root = ORCHESTRATOR_ROOT / "artifacts"
        backend = DbBackend(artifacts_root)
        result = _make_plan_result()
        backend.persist(result)

        metadata = mock_repo.create_run.call_args[1]["metadata"]
        assert metadata["snapshot_dir"] == "artifacts/smoke"

    @patch("testo_core.db.get_repository")
    def test_snapshot_dir_none_when_outside_orchestrator_root(self, mock_get_repo: MagicMock, tmp_path: Path) -> None:
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        backend = DbBackend(tmp_path)
        result = _make_plan_result()
        backend.persist(result)

        metadata = mock_repo.create_run.call_args[1]["metadata"]
        assert metadata["snapshot_dir"] is None


class TestCompositeBackend:
    def test_fans_out_to_all_backends(self, tmp_path: Path) -> None:
        with patch("testo_core.db.get_repository") as mock_get_repo:
            mock_repo = MagicMock()
            mock_get_repo.return_value = mock_repo

            backend = composite_backend(artifacts_root=tmp_path, db=True)
            result = _make_plan_result()
            backend.persist(result)

            assert (tmp_path / "smoke" / "plan_result.json").exists()
            mock_repo.create_run.assert_called_once()

    def test_json_only_when_db_disabled(self, tmp_path: Path) -> None:
        backend = composite_backend(artifacts_root=tmp_path, db=False)
        result = _make_plan_result()
        backend.persist(result)

        assert (tmp_path / "smoke" / "plan_result.json").exists()

    def test_continues_on_backend_failure(self, tmp_path: Path) -> None:
        with patch("testo_core.db.get_repository", side_effect=RuntimeError):
            backend = composite_backend(artifacts_root=tmp_path, db=True)
            result = _make_plan_result()
            backend.persist(result)
            assert (tmp_path / "smoke" / "plan_result.json").exists()

    def test_returns_db_backend_run_id(self, tmp_path: Path) -> None:
        with patch("testo_core.db.get_repository") as mock_get_repo:
            mock_repo = MagicMock()
            fake_record = MagicMock()
            fake_record.id = "run-xyz"
            mock_repo.create_run.return_value = fake_record
            mock_get_repo.return_value = mock_repo

            backend = composite_backend(artifacts_root=tmp_path, db=True)
            result = _make_plan_result()
            run_id = backend.persist(result)

            assert run_id == "run-xyz"

    def test_returns_none_when_db_disabled(self, tmp_path: Path) -> None:
        backend = composite_backend(artifacts_root=tmp_path, db=False)
        result = _make_plan_result()
        run_id = backend.persist(result)
        assert run_id is None
