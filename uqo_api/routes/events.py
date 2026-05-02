from __future__ import annotations

import time
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from uqo_api.dependencies import get_execution_manager
from uqo_api.execution_manager import ExecutionManager, format_sse_message

router = APIRouter(prefix="/api/v1", tags=["events"])


def _event_stream(manager: ExecutionManager, execution_id: str) -> Iterator[str]:
    offset = 0
    while True:
        events, offset, done = manager.read_events_since(execution_id, offset)
        if events:
            for event in events:
                name = str(event.get("event") or "unknown")
                payload = event.get("data")
                if isinstance(payload, dict):
                    yield format_sse_message(name, payload)
        if done:
            return
        yield ": keep-alive\n\n"
        time.sleep(0.2)


@router.get("/executions/{execution_id}/events")
def stream_execution_events(
    execution_id: str,
    manager: ExecutionManager = Depends(get_execution_manager),
) -> StreamingResponse:
    if manager.get(execution_id) is None:
        raise HTTPException(status_code=404, detail=f"Execution not found: {execution_id}")
    return StreamingResponse(_event_stream(manager, execution_id), media_type="text/event-stream")
