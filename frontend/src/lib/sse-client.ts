export type CycleNdjsonEvent =
  | { event: "plan_started"; plan: string; stage_count: number }
  | { event: "stage_started"; stage: string; framework: string; index: number; count: number }
  | {
      event: "stage_finished";
      stage: string;
      framework: string;
      returncode: number;
      duration_s: number;
      log_path: string | null;
      timed_out: boolean;
      internal_failure?: boolean;
      error?: string | null;
    }
  | { event: "plan_aborted"; plan: string; reason: "fail_fast"; completed_stages: number }
  | {
      event: "plan_finished";
      plan: string;
      aggregate_returncode: number;
      exit_code: number;
      duration_s: number;
      stages?: unknown[];
      error?: string | null;
    }
  | { event: "cycle_trigger"; cycle: string; status: "activated" | "resting"; reason: string; matched: string[]; mode: string }
  | { event: "error"; code: string; message: string };

export function subscribeToCycleExecutionEvents(
  eventsUrl: string,
  handlers: {
    onEvent: (event: CycleNdjsonEvent) => void;
    onError?: (error: Event) => void;
  }
): () => void {
  const source = new EventSource(eventsUrl);

  const handle = (eventName: CycleNdjsonEvent["event"]) => (evt: MessageEvent) => {
    handlers.onEvent(JSON.parse(evt.data) as CycleNdjsonEvent);
  };

  source.addEventListener("plan_started", handle("plan_started"));
  source.addEventListener("stage_started", handle("stage_started"));
  source.addEventListener("stage_finished", handle("stage_finished"));
  source.addEventListener("plan_aborted", handle("plan_aborted"));
  source.addEventListener("plan_finished", handle("plan_finished"));
  source.addEventListener("cycle_trigger", handle("cycle_trigger"));
  source.addEventListener("error", handle("error"));

  source.onerror = (evt) => {
    handlers.onError?.(evt);
  };
  return () => source.close();
}
