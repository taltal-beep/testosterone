"""Generate frontend/src/components/mascot/animations.ts from the Python frames.

Run from the repo root after editing animations:
    python -m testo_core.mascot.export_ts
"""

from __future__ import annotations

from pathlib import Path

from . import ANIMATIONS, PALETTE

HEADER = """\
// GENERATED FILE - do not edit by hand.
// Source of truth: testo_core/mascot/__init__.py
// Regenerate with: python -m testo_core.mascot.export_ts

export type PixelPalette = Record<string, string>;
export type PixelFrame = string[];
export type PixelAnimation = PixelFrame[];
"""


def render_ts() -> str:
    lines = [HEADER]
    lines.append("export const MASCOT_PALETTE: PixelPalette = {")
    for char, color in PALETTE.items():
        lines.append(f'  "{char}": "{color}",')
    lines.append("};\n")
    for name, animation in ANIMATIONS.items():
        lines.append(f"export const {name.upper()}: PixelAnimation = [")
        for frame in animation:
            lines.append("  [")
            for row in frame:
                lines.append(f'    "{row}",')
            lines.append("  ],")
        lines.append("];\n")
    names = ", ".join(f'"{n}": {n.upper()}' for n in ANIMATIONS)
    lines.append(f"export const ANIMATIONS: Record<string, PixelAnimation> = {{ {names} }};")
    return "\n".join(lines) + "\n"


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    target = repo_root / "frontend" / "src" / "components" / "mascot" / "animations.ts"
    target.write_text(render_ts(), encoding="utf-8")
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
