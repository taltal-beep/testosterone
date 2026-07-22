from __future__ import annotations

import re
import sys
from pathlib import Path

VERSION_HEADING_RE = re.compile(r"^## \[(?P<version>[^\]]+)\](?: - (?P<date>\d{4}-\d{2}-\d{2}))?\s*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def check(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"{path} does not exist"]

    headings = [
        m.group("version")
        for line in path.read_text().splitlines()
        if (m := VERSION_HEADING_RE.match(line))
    ]

    if not headings:
        errors.append("No '## [...]' version headings found")
        return errors

    unreleased_count = sum(1 for h in headings if h == "Unreleased")
    if unreleased_count != 1:
        errors.append(f"Expected exactly one '## [Unreleased]' heading, found {unreleased_count}")

    for heading in headings:
        if heading == "Unreleased":
            continue
        if not re.match(r"^\d+\.\d+\.\d+$", heading):
            errors.append(f"Version heading '{heading}' is not a valid semver (x.y.z)")

    with path.open() as f:
        for line in f:
            m = VERSION_HEADING_RE.match(line)
            if m and m.group("version") != "Unreleased" and not m.group("date"):
                errors.append(f"Version heading '{m.group('version')}' is missing a YYYY-MM-DD date")

    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = check(root / "CHANGELOG.md")
    if errors:
        for error in errors:
            print(f"CHANGELOG.md format error: {error}", file=sys.stderr)
        return 1
    print("CHANGELOG.md format OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
