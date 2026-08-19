# Freebuff Multi-Agent Software Development System

An asyncio-native orchestration layer written in Python that spawns a team of
specialized AI agents and coordinates them to turn a raw product idea into a
structured **PRD**, an **architecture blueprint**, **runnable code**, and a
**QA audit report** — all exposed through a FastAPI REST API with live agent
log streaming.

## The agent team

| Agent | File | Responsibility |
| --- | --- | --- |
| Product Manager | `src/agents/product_manager.py` | Ingests the raw idea and emits a structured PRD, user stories, and an itemized, role-assigned task queue. |
| Architect | `src/agents/architect.py` | Translates the PRD into a project folder schema, an ERD with fields/relations, and a REST API contract. |
| Developer | `src/agents/developer.py` | Generates complete, runnable Python files (Pydantic models, FastAPI routers, main app, pytest suites). |
| QA Auditor | `src/agents/qa_auditor.py` | Statically audits generated code for syntax errors, missing edge cases, and security vulnerabilities; emits a scored report. |

## How it works

`AgentManager` (in `src/orchestrator.py`) manages the full sprint lifecycle:

- **Agent state transitions** — every agent moves `idle -> ready -> working -> done`
  (or `blocked` on failure); every transition is recorded in `sprint.agent_events`.
- **Task delegation** — each delegation is recorded as an `ExecutionTask` with
  pending/in-progress/completed/failed status.
- **Inter-agent message passing** — the `Reporter` bus records handoff `Message`
  records between agents as artifacts move down the pipeline.

Two workflow modes:

1. **Sequential** — a linear pipeline: `PM -> Architect -> Developer -> QA`.
2. **Parallel** — the PM's itemized task queue is fanned out: each developer
   sub-task (with its own QA pass) runs concurrently via `asyncio.gather`.

## Project layout

```
src/
├── models.py              # Pydantic validation models (inputs, outputs, records)
├── orchestrator.py        # AgentManager + SprintStore (sequential/parallel modes)
├── main.py                # FastAPI app: sprint endpoints + SSE log streaming
└── agents/
    ├── base.py            # Async Reporter bus + BaseAgent
    ├── specs.py           # Shared feature/entity vocabulary
    ├── product_manager.py
    ├── architect.py
    ├── developer.py
    └── qa_auditor.py
tests/
├── test_agents.py         # Per-agent unit tests
└── test_orchestrator.py   # Orchestrator + REST API tests
data/sprints/              # JSON persistence of completed sprints (auto-created)
```

## Setup (step by step)

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the test suite (should report all passing)
pytest -q
```

## Start the server

```bash
# From the project root, with the virtual environment active:
uvicorn src.main:app --reload --port 8000
# or:
python -m src.main
```

The API is then available at <http://127.0.0.1:8000> — interactive docs at
<http://127.0.0.1:8000/docs>.

## API usage

### 1. Trigger a run

```bash
curl -X POST http://127.0.0.1:8000/sprints/create \
  -H "Content-Type: application/json" \
  -d '{"idea": "Build a task management app with user authentication and notifications", "mode": "parallel"}'
```

`mode` is `sequential` (default) or `parallel`. Returns the `sprint_id`
immediately; execution happens in the background.

### 2. Poll the status

```bash
curl http://127.0.0.1:8000/sprints/<sprint_id>/status
```

Includes overall status, per-agent lifecycle states, progress, and the
delegated task list.

### 3. Fetch the artifacts

```bash
curl http://127.0.0.1:8000/sprints/<sprint_id>/artifacts
```

Returns every artifact the team produced: `prd`, `user_stories`, `task_queue`,
`folder_schema`, `erd`, `api_contract`, `source_code` (one per parallel
sub-task), and `audit_report`.

### 4. Stream live agent logs

```bash
curl -N http://127.0.0.1:8000/sprints/<sprint_id>/logs/stream
```

Server-Sent Events stream; each line is `data: {"timestamp": ..., "role": ...,
"level": ..., "message": ...}`. Ends with a `{"type": "done", "status": ...}`
event. A JSON variant is available at `GET /sprints/<sprint_id>/logs`.

### Other endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /sprints` | List all sprints |
| `GET /health` | Liveness probe |

## Testing

```bash
pytest -q
```

The suite covers:

- Every agent's structured outputs (PRD shape, ERD fields/relations, API
  contract, task queue role assignment).
- **Runnable-code proof**: the developer's generated project is written to a
  temp directory and its own `pytest` suite is executed.
- QA auditor behavior: clean code passes with a perfect score; deliberately
  broken/insecure code is flagged with the right severities.
- Orchestrator behavior in both modes: artifact ordering, state transitions,
  handoff messages, task delegation, persistence round-trips.
- The full REST API: create → poll → artifacts → SSE log streaming → 404s → 422s.

## Generated code

The Developer agent's `source_code` artifact is a complete runnable project
(FastAPI + Pydantic + pytest). To materialize it locally, e.g.:

```bash
curl -s http://127.0.0.1:8000/sprints/<sprint_id>/artifacts \
  | python -c "import json,sys; d=json.load(sys.stdin); a=[x for x in d['artifacts'] if x['kind']=='source_code'][0]; [__import__('pathlib').Path(p).write_text(c) for p,c in a['content']['files'].items()]; print('wrote', len(a['content']['files']), 'files')"
```

then `cd <project-name> && pip install -r requirements.txt && pytest` and
`uvicorn src.main:app --reload`.
