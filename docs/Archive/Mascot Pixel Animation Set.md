# Mascot Pixel Animation Set

**Date**: 2026-07-04
**Status**: Implemented

## Why

The original mascot (rounded all-blue flex glyph in `frontend/src/components/mascot/index.tsx`) read badly — feedback was blunt: it looked like a sex toy. The redesign moves to a skin-tone palette with dark outlines, real anatomy (knuckled fist, wristband, bicep), and multi-frame animations that work in both the React UI and the terminal.

## Design

- **Single source of truth**: `testo_core/mascot/__init__.py`. A frame is a list of equal-length strings; each character indexes `PALETTE` (`"."` = transparent). Sprites are composed with `_paste`/`_mirror` helpers.
- **Four animations**:
  - `flex` (20×18, 6 frames) — bicep pumps relaxed → peak with a shine sparkle. Success/celebration.
  - `smash` (22×18, 5 frames) — hammer fist drops from off-screen through a stack of bricks. Heavy work in progress.
  - `hurt` (20×18, 7 frames) — spark flies in, star burst on the bicep, arm droops with bandage and falling sweat drop. Failure.
  - `gloves` (26×13, 6 frames) — red and blue gloves wind up, punch with an impact burst, recoil. Comparisons/versus (delta engine).
- **Brand color** stays as the blue wristband (`#3b82f6` / `#1d4ed8`) on the skin-toned arm; gloves reuse red + brand blue.

## Renderers

- **Terminal**: `testo_core/mascot/render.py` — truecolor ANSI using `▀` half-blocks (two pixel rows per text line). `play()` animates in place with cursor control; `frame_to_ansi()` renders a still. Demo: `python -m testo_core.mascot flex` (also `--still`, `--fps`, `--loops`). `frame_to_png()` (stdlib-only PNG writer) exists for docs/previews.
- **React**: `frontend/src/components/mascot/`
  - `animations.ts` — **generated**, do not edit. Regenerate after changing frames: `python -m testo_core.mascot.export_ts`.
  - `PixelArt.tsx` — SVG grid renderer (now aspect-ratio correct for non-square grids).
  - `AnimatedPixelArt.tsx` — cycles frames on an interval; `playing={false}` shows a chosen still frame.
  - `index.tsx` — `MuscleLogo` (still peak flex), `MuscleFlex` (flex), `MuscleDefeated` (hurt), `MuscleSmash` (smash), `GlovesPunch` (gloves), `MuscleShrug` (still, unchanged pose recolored).

## Usage map

| Component | Where | State |
|---|---|---|
| `MuscleLogo` | AppShell header | always |
| `MuscleFlex` | RunPanel | run passed |
| `MuscleDefeated` | RunPanel | run failed |
| `MuscleShrug` | empty states (Cycles, History, Dashboard) | no data |
| `MuscleSmash` | available, not yet wired | candidate: run executing |
| `GlovesPunch` | available, not yet wired | candidate: Compare page |

## Editing workflow

1. Edit frames in `testo_core/mascot/__init__.py`.
2. Preview: `python -m testo_core.mascot <name>` in a terminal, or export PNG contact sheets with `frame_to_png`.
3. Regenerate the frontend data: `python -m testo_core.mascot.export_ts`.
4. Commit both files together.
