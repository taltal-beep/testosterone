from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


def _try_import_allure():
    try:
        import allure  # type: ignore

        return allure
    except Exception:
        return None


@contextmanager
def step(title: str) -> Iterator[None]:
    allure = _try_import_allure()
    if allure is None:
        yield
        return
    with allure.step(title):
        yield


def attach_json(name: str, data: Any) -> None:
    allure = _try_import_allure()
    if allure is None:
        return
    try:
        body = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    except Exception:
        body = repr(data)
    allure.attach(body, name=name, attachment_type=getattr(allure.attachment_type, "JSON", None) or allure.attachment_type.TEXT)

