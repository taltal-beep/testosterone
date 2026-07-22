"""Render mascot frames as ANSI half-blocks (terminal) or PNG (previews)."""

from __future__ import annotations

import struct
import sys
import time
import zlib

from . import ANIMATIONS, PALETTE, Animation, Frame

RESET = "\x1b[0m"


def _hex_rgb(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def frame_to_ansi(frame: Frame, palette: dict[str, str] = PALETTE) -> str:
    """Render a frame with U+2580 half-blocks: two grid rows per text line."""
    width = max(len(row) for row in frame)
    rows = [row.ljust(width, ".") for row in frame]
    if len(rows) % 2:
        rows.append("." * width)
    lines = []
    for top, bottom in zip(rows[0::2], rows[1::2], strict=True):
        line = []
        for tc, bc in zip(top, bottom, strict=True):
            tcol, bcol = palette.get(tc), palette.get(bc)
            if tcol is None and bcol is None:
                line.append(f"{RESET} ")
                continue
            parts = []
            if tcol:
                r, g, b = _hex_rgb(tcol)
                parts.append(f"38;2;{r};{g};{b}")
            else:
                parts.append("39")
            if bcol:
                r, g, b = _hex_rgb(bcol)
                parts.append(f"48;2;{r};{g};{b}")
            else:
                parts.append("49")
            glyph = "▀" if tcol else "▄"
            if tcol is None:
                # only bottom colored: draw lower half-block with fg=bottom
                r, g, b = _hex_rgb(bcol)
                parts = [f"38;2;{r};{g};{b}", "49"]
            line.append("\x1b[" + ";".join(parts) + "m" + glyph)
        lines.append("".join(line) + RESET)
    return "\n".join(lines)


def play(animation: Animation, fps: float = 6.0, loops: int = 3,
         palette: dict[str, str] = PALETTE, out=sys.stdout) -> None:
    """Play an animation in-place in the terminal."""
    height = (max(len(f) for f in animation) + 1) // 2
    delay = 1.0 / fps
    out.write("\x1b[?25l")  # hide cursor
    try:
        first = True
        for _ in range(loops):
            for frame in animation:
                if not first:
                    out.write(f"\x1b[{height}F")
                out.write(frame_to_ansi(frame, palette) + "\n")
                out.flush()
                first = False
                time.sleep(delay)
    finally:
        out.write("\x1b[?25h")
        out.flush()


def frame_to_png(frame: Frame, path: str, scale: int = 12,
                 palette: dict[str, str] = PALETTE,
                 background: str | None = "#ffffff") -> None:
    """Write a frame as a PNG using only the stdlib (for previews/docs)."""
    width = max(len(row) for row in frame)
    rows = [row.ljust(width, ".") for row in frame]
    bg = _hex_rgb(background) if background else (0, 0, 0)
    raw = bytearray()
    for row in rows:
        scanline = bytearray()
        for ch in row:
            rgb = _hex_rgb(palette[ch]) if ch in palette else bg
            scanline += bytes(rgb) * scale
        for _ in range(scale):
            raw += b"\x00" + scanline
    w, h = width * scale, len(rows) * scale

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data)))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw)))
           + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)


__all__ = ["ANIMATIONS", "PALETTE", "frame_to_ansi", "play", "frame_to_png"]
