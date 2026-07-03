import { PixelArt } from "./PixelArt";

export interface MascotProps {
  size?: number;
  animate?: boolean;
  className?: string;
}

// Flexed bicep, fist raised — the brand mark and the "run passed" celebration.
const FLEX_GRID = [
  "................",
  "....ooo.........",
  "...owwso........",
  "..owssso........",
  "..ossssso.......",
  "..osssso........",
  "...ossso........",
  "....osso........",
  "....odsso.......",
  "....odssso......",
  "...odssssso.....",
  "..odsssshsso....",
  "..ossssshhsso...",
  "..oosssssssoo...",
  "....oosssoo.....",
  "......ooo......."
];

// Drooping arm with a sweat drop — the "run failed" reaction.
const DEFEATED_GRID = [
  "................",
  "..oooooo........",
  ".ossssssoo......",
  ".osssssssso.....",
  "..oosssssso..t..",
  "....oossso...t..",
  "......osso..tt..",
  "......osso......",
  ".....osso.......",
  ".....osso.......",
  "....osso........",
  "....osso........",
  "...owwo.........",
  "...owwo.........",
  "....oo..........",
  "................"
];

// Open palm turned up with a floating question mark — empty states.
const SHRUG_GRID = [
  "................",
  "..........qqq...",
  ".........q...q..",
  ".............q..",
  "............q...",
  "...........q....",
  "................",
  "...........q....",
  "................",
  ".w.w.w..........",
  ".owwwo..........",
  ".osssoo.........",
  ".ossssoo........",
  "..osssssoooooo..",
  "...ossssssssso..",
  "....oooooooo...."
];

export function MuscleLogo({ size = 24, className }: MascotProps) {
  return <PixelArt grid={FLEX_GRID} size={size} className={className} title="Testo" />;
}

export function MuscleFlex({ size = 96, animate = false, className }: MascotProps) {
  return (
    <PixelArt
      grid={FLEX_GRID}
      size={size}
      className={`${animate ? "animate-muscle-flex " : ""}${className ?? ""}`}
      title="Flexing muscle — success"
    />
  );
}

export function MuscleDefeated({ size = 96, animate = false, className }: MascotProps) {
  return (
    <PixelArt
      grid={DEFEATED_GRID}
      size={size}
      className={`${animate ? "animate-muscle-droop " : ""}${className ?? ""}`}
      title="Defeated muscle — failure"
    />
  );
}

export function MuscleShrug({ size = 96, className }: MascotProps) {
  return <PixelArt grid={SHRUG_GRID} size={size} className={className} title="Shrugging muscle — nothing here yet" />;
}
