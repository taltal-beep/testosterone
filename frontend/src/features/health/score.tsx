/** Shared by the health score and the AI review: one colour scale for every 0-100 score. */

type Tone = "success" | "warn" | "danger" | "neutral";

/** Green from 80, amber from 60, red below; grey when there is no score. */
export function scoreTone(score: number | null | undefined): Tone {
  if (score == null) return "neutral";
  if (score >= 80) return "success";
  if (score >= 60) return "warn";
  return "danger";
}

export const TONE_TEXT: Record<Tone, string> = {
  success: "text-success-300",
  warn: "text-warn-300",
  danger: "text-danger-300",
  neutral: "text-ink-400"
};

export const TONE_BAR: Record<Tone, string> = {
  success: "bg-success-400",
  warn: "bg-warn-400",
  danger: "bg-danger-400",
  neutral: "bg-ink-600"
};

/** A 0-100 score as a ring, the number and the grade in the middle. */
export function ScoreRing({ score, grade, label, size = 132 }: { score: number | null | undefined; grade?: string | null; label: string; size?: number }) {
  const tone = scoreTone(score);
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const filled = score == null ? 0 : (circumference * score) / 100;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} role="img" aria-label={score == null ? `${label}: no score yet` : `${label}: ${score} out of 100${grade ? `, grade ${grade}` : ""}`}>
      <svg viewBox="0 0 120 120" className={`h-full w-full -rotate-90 ${TONE_TEXT[tone]}`} aria-hidden>
        <circle cx="60" cy="60" r={radius} fill="none" strokeWidth="10" className="stroke-ink-800" />
        <circle cx="60" cy="60" r={radius} fill="none" strokeWidth="10" stroke="currentColor" strokeLinecap="round" strokeDasharray={`${filled} ${circumference}`} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center" aria-hidden>
        <span className="text-3xl font-bold text-white">{score ?? "–"}</span>
        <span className="text-xs text-ink-300">{grade ? `of 100 · ${grade}` : "of 100"}</span>
      </div>
    </div>
  );
}

