"""Deterministic stand-in for a framework binary (pytest/behave/behavex).

The engine test suite launches this script through :class:`EchoAdapter` so a
"stage" is a real subprocess with fully scripted behaviour:

    echo.py --text hello --exit-code 1 --sleep 0.1 --print-env UQO_LAST_TEST_TYPE
"""

from __future__ import annotations

import argparse
import os
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exit-code", type=int, default=0)
    parser.add_argument("--text", default="echo-stage")
    parser.add_argument("--stderr-text", default=None)
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument("--print-env", action="append", default=[])
    args = parser.parse_args()

    print(args.text, flush=True)
    for name in args.print_env:
        print(f"{name}={os.environ.get(name, '')}", flush=True)
    if args.stderr_text is not None:
        print(args.stderr_text, file=sys.stderr, flush=True)
    if args.sleep:
        time.sleep(args.sleep)
    return args.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
