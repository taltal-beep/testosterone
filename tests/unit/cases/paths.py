from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PathCase:
    name: str
    value: Path


def common_path_cases(tmp_path: Path) -> list[PathCase]:
    return [
        PathCase("tmp_root", tmp_path),
        PathCase("child", tmp_path / "child"),
        PathCase("nested", tmp_path / "a" / "b" / "c"),
        PathCase("dot", Path(".")),
        PathCase("dotdot", Path("..")),
        PathCase("relative_file", Path("relative.txt")),
        PathCase("absolute", tmp_path.resolve()),
    ]
