// Plays a pixel animation by cycling PixelArt frames on a timer.

import { useEffect, useState } from "react";
import { PixelArt } from "./PixelArt";
import type { PixelAnimation, PixelPalette } from "./animations";

export interface AnimatedPixelArtProps {
  animation: PixelAnimation;
  /** Frames per second while playing. */
  fps?: number;
  /** When false, renders stillFrame without a timer. */
  playing?: boolean;
  /** Frame index to show while not playing (default: first frame). */
  stillFrame?: number;
  palette?: PixelPalette;
  size?: number;
  className?: string;
  title?: string;
}

export function AnimatedPixelArt({
  animation,
  fps = 6,
  playing = true,
  stillFrame = 0,
  palette,
  size,
  className,
  title
}: AnimatedPixelArtProps) {
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    if (!playing || animation.length < 2) return;
    const id = window.setInterval(() => {
      setFrame((current) => (current + 1) % animation.length);
    }, 1000 / fps);
    return () => window.clearInterval(id);
  }, [playing, animation, fps]);

  const grid = playing ? animation[frame % animation.length] : animation[stillFrame % animation.length];
  return <PixelArt grid={grid} palette={palette} size={size} className={className} title={title} />;
}
