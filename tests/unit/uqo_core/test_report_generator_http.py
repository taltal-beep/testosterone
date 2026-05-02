"""HTTP helpers in ``report_generator`` (mock server)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from uqo_core.report_generator import start_report_server


def test_start_report_server_starts_thread(tmp_path: Path) -> None:
    root = tmp_path / "r"
    root.mkdir()
    (root / "index.html").write_text("ok", encoding="utf-8")

    mock_httpd = MagicMock()
    mock_thread = MagicMock()

    with patch("uqo_core.report_generator.http.server.ThreadingHTTPServer", return_value=mock_httpd):
        with patch("uqo_core.report_generator.threading.Thread", return_value=mock_thread) as thread_cls:
            srv = start_report_server(report_dir=root, port=9123)
    assert srv.port == 9123
    thread_cls.assert_called_once()
