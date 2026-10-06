from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StringCase:
    name: str
    value: str


def common_string_cases() -> list[StringCase]:
    return [
        StringCase("empty", ""),
        StringCase("space", " "),
        StringCase("whitespace", " \t\r\n "),
        StringCase("ascii", "abcXYZ123"),
        StringCase("unicode", "ユーザー✓"),
        StringCase("quotes", "\"'`"),
        StringCase("path_like", "../etc/passwd"),
        StringCase("json_like", '{"a":1,"b":"x"}'),
        StringCase("sql_injection_1", "' OR '1'='1"),
        StringCase("sql_injection_2", "admin; DROP TABLE users; --"),
        StringCase("null_byte", "a\0b"),
        StringCase("long_1k", "x" * 1024),
    ]
