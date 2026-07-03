// Shared pixel-grid renderer for the Testo arm-muscle mascot family.
// Each mascot declares a character grid; every char maps to a palette color,
// "." is transparent. shape-rendering keeps edges crisp at any size.

export type PixelPalette = Record<string, string>;

export const MASCOT_PALETTE: PixelPalette = {
  o: "#1d4ed8", // outline (deep brand blue)
  s: "#3b82f6", // muscle fill (brand blue)
  h: "#93c5fd", // highlight
  d: "#2563eb", // shading
  w: "#ececf1", // wristband / accents
  t: "#7dd3fc", // sweat drop
  q: "#9b9ba4"  // question mark / neutral detail
};

export interface PixelArtProps {
  grid: string[];
  palette?: PixelPalette;
  /** Rendered width/height in px (square). */
  size?: number;
  className?: string;
  title?: string;
}

export function PixelArt({ grid, palette = MASCOT_PALETTE, size = 64, className, title }: PixelArtProps) {
  const rows = grid.length;
  const cols = Math.max(0, ...grid.map((row) => row.length));
  return (
    <svg
      viewBox={`0 0 ${cols} ${rows}`}
      width={size}
      height={size}
      shapeRendering="crispEdges"
      role="img"
      aria-label={title ?? "Testo mascot"}
      className={className}
    >
      {title ? <title>{title}</title> : null}
      {grid.flatMap((row, y) =>
        Array.from(row).map((char, x) => {
          const fill = palette[char];
          if (!fill) return null;
          return <rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} fill={fill} />;
        })
      )}
    </svg>
  );
}
