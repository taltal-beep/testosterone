"""Transitional ``uqo`` console script that delegates to the new Typer app.

The distribution still ships a ``uqo`` entry-point so existing CI pipelines
and Docker images keep working; this module prints a one-line deprecation
notice on stderr and immediately forwards to :func:`testo_core.cli.app.main`.
"""

from __future__ import annotations

import sys

_NOTICE = (
    "[testo] The 'uqo' command is deprecated and will be removed in a future release. "
    "Use 'testo' instead.\n"
)


def main(argv: list[str] | None = None) -> int:
    sys.stderr.write(_NOTICE)
    sys.stderr.flush()
    from testo_core.cli.app import main as testo_main

    return testo_main(argv)


if __name__ == "__main__":
    sys.exit(main())
