"""Console-script entry-point for ``testo-ui``.

Streamlit is awkward to launch programmatically — the standard idiom is to
shell out to ``streamlit run <path-to-app.py>``.  This wrapper resolves the
packaged ``streamlit_app.py`` so users can simply run ``testo-ui`` from any
directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

_APP_PATH = Path(__file__).with_name("streamlit_app.py")


def main(argv: list[str] | None = None) -> int:
    try:
        from streamlit.web import cli as stcli  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        sys.stderr.write(
            "streamlit is not installed. Run `pip install testo-core[ui]` first.\n"
        )
        return 1

    args = ["streamlit", "run", str(_APP_PATH), "--server.headless=true"]
    if argv:
        args.extend(argv)
    sys.argv = args
    try:
        return int(stcli.main() or 0)
    except SystemExit as exc:
        return int(exc.code or 0)


if __name__ == "__main__":
    sys.exit(main())
