import { API_BASE, type AttachmentItem } from "../../lib/api-client";

function href(attachment: AttachmentItem): string {
  return `${API_BASE}/${attachment.url}`;
}

function size(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * What the last failing run kept for this test: screenshots and videos shown
 * in place, a Playwright trace with the command that opens it, anything else
 * as a download.
 */
export function Attachments({ items }: { items: AttachmentItem[] }) {
  if (items.length === 0) return null;
  const images = items.filter((a) => a.kind === "image");
  const videos = items.filter((a) => a.kind === "video");
  const others = items.filter((a) => a.kind !== "image" && a.kind !== "video");

  return (
    <div className="mt-4 space-y-3" data-testid="attachments">
      {images.length > 0 || videos.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {images.map((a) => (
            <a key={a.url} href={href(a)} target="_blank" rel="noreferrer" className="block">
              <img
                src={href(a)}
                alt={`${a.name} from the failing run`}
                loading="lazy"
                className="max-h-64 w-full rounded-lg border border-white/10 bg-ink-900 object-contain"
              />
            </a>
          ))}
          {videos.map((a) => (
            <video
              key={a.url}
              src={href(a)}
              controls
              preload="metadata"
              aria-label={`${a.name} from the failing run`}
              className="max-h-64 w-full rounded-lg border border-white/10 bg-ink-900"
            />
          ))}
        </div>
      ) : null}
      {others.length > 0 ? (
        <ul className="space-y-1.5 text-sm">
          {others.map((a) => (
            <li key={a.url} className="flex flex-wrap items-baseline gap-x-2">
              <a href={href(a)} download className="-my-1 inline-block py-1 text-brand-300 hover:underline">
                {a.kind === "trace" ? "Download trace" : a.name}
              </a>
              <span className="text-xs text-ink-400">{size(a.size_bytes)}</span>
              {a.kind === "trace" ? (
                <span className="text-xs text-ink-400">
                  open it with <code className="font-mono text-ink-200">npx playwright show-trace trace.zip</code> or at{" "}
                  <a href="https://trace.playwright.dev" target="_blank" rel="noreferrer" className="text-brand-300 hover:underline">
                    trace.playwright.dev
                  </a>
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
