"""Sleep far longer than any ``timeout_s`` used in tests (stage-timeout fixture)."""

from __future__ import annotations

import time

if __name__ == "__main__":
    print("hanging", flush=True)
    time.sleep(3600)
