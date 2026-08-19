"""FastAPI application exposing the multi-agent orchestration engine.

Endpoints
---------
* ``POST /sprints/create``            trigger a new agent run
* ``GET  /sprints/{id}/status``       poll sprint status and agent states
* ``GET  /sprints/{id}/artifacts``    fetch every artifact the team produced
* ``GET  /sprints/{id}/logs``         fetch logs as JSON
* ``GET  /sprints/{id}/logs/stream``  stream live agent logs over SSE
* ``GET  /sprints``                   list known sprints
* ``GET  /health``                    liveness probe
"""

from __future__ import annotations

import asyncio
import json
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from .models import (
    LogEntry,
    SprintArtifactsResponse,
    SprintCreateRequest,
    SprintCreateResponse,
    SprintListResponse,
    SprintStatus,
    SprintStatusResponse,
    SprintSummary,
    TaskStatus,
)
from .orchestrator import AgentManager

app = FastAPI(
    title="Freebuff Multi-Agent Development System",
    version="1.0.0",
    description=(
        "Spawns a team of specialized AI agents (product manager, architect, "
        "developer, QA auditor) that turn a raw idea into a PRD, architecture, "
        "runnable code, and an audit report."
    ),
)

manager = AgentManager()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/sprints/create", response_model=SprintCreateResponse, status_code=201)
async def create_sprint(request: SprintCreateRequest) -> SprintCreateResponse:
    """Trigger a new agent run and return immediately; execution is async."""
    sprint = await manager.start(request.idea, request.mode)
    return SprintCreateResponse(
        sprint_id=sprint.id,
        status=sprint.status,
        mode=sprint.mode,
        idea=sprint.idea,
        created_at=sprint.created_at,
    )


@app.get("/sprints", response_model=SprintListResponse)
async def list_sprints() -> SprintListResponse:
    sprints = [
        SprintSummary(
            sprint_id=s.id,
            idea=s.idea,
            mode=s.mode,
            status=s.status,
            created_at=s.created_at,
        )
        for s in manager.store.all()
    ]
    return SprintListResponse(sprints=sprints)


@app.get("/sprints/{sprint_id}/status", response_model=SprintStatusResponse)
async def sprint_status(sprint_id: str) -> SprintStatusResponse:
    """Poll the status of a sprint and every agent's lifecycle state."""
    sprint = manager.store.get(sprint_id)
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")
    total = len(sprint.tasks)
    completed = sum(1 for t in sprint.tasks if t.status is TaskStatus.COMPLETED)
    progress = round(completed / total, 4) if total else 0.0
    return SprintStatusResponse(
        sprint_id=sprint.id,
        status=sprint.status,
        mode=sprint.mode,
        idea=sprint.idea,
        error=sprint.error,
        progress=progress,
        agents=sprint.agents,
        tasks=sprint.tasks,
        created_at=sprint.created_at,
        completed_at=sprint.completed_at,
    )


@app.get("/sprints/{sprint_id}/artifacts", response_model=SprintArtifactsResponse)
async def sprint_artifacts(sprint_id: str) -> SprintArtifactsResponse:
    """Return every artifact (PRD, ERD, code, audit report...) produced so far."""
    sprint = manager.store.get(sprint_id)
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return SprintArtifactsResponse(sprint_id=sprint.id, artifacts=sprint.artifacts)


@app.get("/sprints/{sprint_id}/logs", response_model=List[LogEntry])
async def sprint_logs(sprint_id: str) -> List[LogEntry]:
    """Return the collected agent log lines as plain JSON."""
    sprint = manager.store.get(sprint_id)
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return list(sprint.logs)


@app.get("/sprints/{sprint_id}/logs/stream")
async def stream_sprint_logs(sprint_id: str) -> StreamingResponse:
    """Stream live agent logs over Server-Sent Events (``text/event-stream``)."""
    sprint = manager.store.get(sprint_id)
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")

    async def generate():
        yield "retry: 3000\n\n"
        cursor = 0
        while True:
            snapshot = list(sprint.logs)
            while cursor < len(snapshot):
                entry = snapshot[cursor]
                cursor += 1
                yield f"data: {json.dumps(entry.model_dump(mode='json'))}\n\n"
            if sprint.status in (SprintStatus.COMPLETED, SprintStatus.FAILED):
                break
            await asyncio.sleep(0.2)
        done = {"type": "done", "status": sprint.status.value}
        yield f"data: {json.dumps(done)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=True)
