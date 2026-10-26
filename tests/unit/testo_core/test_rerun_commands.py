"""Rerun commands for a run's failing tests (testo_core/services/rerun_commands.py)."""

from __future__ import annotations

import pytest

from testo_core.services.rerun_commands import (
    MAX_TESTS,
    FailingCase,
    pytest_node_id,
    rerun_commands,
)


@pytest.mark.parametrize(
    ("full_name", "name", "expected"),
    [
        # Allure pytest: module#function, module.Class#method.
        (
            "tests.api.test_orders#test_create",
            "test_create",
            "tests/api/test_orders.py::test_create",
        ),
        (
            "tests.api.test_orders.TestCancel#test_twice",
            "test_twice",
            "tests/api/test_orders.py::TestCancel::test_twice",
        ),
        # JUnit from pytest --junitxml: classname.name.
        ("tests.ui.test_login.test_form", "test_form", "tests/ui/test_login.py::test_form"),
        # Already a node id.
        ("tests/test_a.py::test_x[1]", "test_x[1]", "tests/test_a.py::test_x[1]"),
        # Not a Python test module.
        ("LoginSpec.rejects a wrong password", "rejects a wrong password", None),
    ],
)
def test_pytest_node_id(full_name: str, name: str, expected: str | None) -> None:
    assert pytest_node_id(full_name, name) == expected


def test_one_command_per_runner() -> None:
    cases = [
        FailingCase("test_create", "tests.api.test_orders#test_create", "", "api"),
        FailingCase("test_create", "tests.api.test_orders#test_create", "", "api"),  # retried twice
        FailingCase("checkout (total)", "cart.spec.ts › checkout (total)", "", "e2e"),
        FailingCase("Login works", "features/login.feature", "", "bdd"),
    ]
    commands = rerun_commands(cases, {"api": "pytest", "e2e": "playwright", "bdd": "behave"})

    assert commands == [
        "pytest tests/api/test_orders.py::test_create",
        "npx playwright test --grep 'checkout \\(total\\)'",
        "behave --name '^Login works$'",
    ]


def test_ingested_junit_gets_pytest_only_for_python_modules() -> None:
    py = FailingCase("test_form", "tests.ui.test_login.test_form", "", "junit")
    jest = FailingCase("renders", "Button renders", "", "junit")

    assert rerun_commands([py], {"junit": "junit"}) == ["pytest tests/ui/test_login.py::test_form"]
    assert rerun_commands([jest], {"junit": "junit"}) == []


def test_too_many_failures_get_no_command() -> None:
    cases = [
        FailingCase(f"test_{i}", f"tests.test_a#test_{i}", "", "unit") for i in range(MAX_TESTS + 1)
    ]
    assert rerun_commands(cases, {"unit": "pytest"}) == []
