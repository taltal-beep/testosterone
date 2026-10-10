from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JsonCase:
    name: str
    value: Any


def common_json_cases() -> list[JsonCase]:
    return [
        JsonCase("empty_obj", {}),
        JsonCase("simple_obj", {"k": "v"}),
        JsonCase("numbers", {"a": 0, "b": -1, "c": 2**31 - 1}),
        JsonCase("mixed_list", {"list": [1, "two", None, True, {"x": "y"}]}),
        JsonCase("deep", {"a": {"b": {"c": {"d": {"e": 1}}}}}),
        JsonCase("sqli", {"q": "' OR '1'='1"}),
        JsonCase("special_chars", {"s": " \t\r\n \" ' \\ /"}),
    ]
