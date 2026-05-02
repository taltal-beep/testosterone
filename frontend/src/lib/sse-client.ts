export type ExecutionEvent =
  | { event: "log"; data: { stream: string; line: string; ts: number } }
  | {
      event: "run_result";
      data: { run_id: string | null; test_type: string; returncode: number; started_at: number; finished_at: number; cwd: string };
    }
  | { event: "summary"; data: Record<string, unknown> };

export function subscribeToExecutionEvents(
  eventsUrl: string,
  handlers: {
    onEvent: (event: ExecutionEvent) => void;
    onError?: (error: Event) => void;
  }
): () => void {
  const source = new EventSource(eventsUrl);
  source.addEventListener("log", (evt: MessageEvent) => {
    handlers.onEvent({ event: "log", data: JSON.parse(evt.data) });
  });
  source.addEventListener("run_result", (evt: MessageEvent) => {
    handlers.onEvent({ event: "run_result", data: JSON.parse(evt.data) });
  });
  source.addEventListener("summary", (evt: MessageEvent) => {
    handlers.onEvent({ event: "summary", data: JSON.parse(evt.data) });
  });
  source.onerror = (evt) => {
    handlers.onError?.(evt);
  };
  return () => source.close();
}
