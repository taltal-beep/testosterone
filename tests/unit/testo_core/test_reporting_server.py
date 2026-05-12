"""Tests for local report server helpers."""

from __future__ import annotations

import socket

from testo_core.reporting.server import find_free_port, resolve_serve_port


def test_find_free_port_returns_ephemeral() -> None:
    p = find_free_port()
    assert isinstance(p, int)
    assert 1 <= p <= 65535


def test_resolve_serve_port_zero_means_ephemeral() -> None:
    p = resolve_serve_port("127.0.0.1", 0)
    assert p != 0


def test_resolve_serve_port_falls_back_when_preferred_busy() -> None:
    host = "127.0.0.1"
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    holder.bind((host, 0))
    busy = int(holder.getsockname()[1])
    holder.listen(1)
    try:
        chosen = resolve_serve_port(host, busy)
        assert chosen != busy
    finally:
        holder.close()
