"""Tests for the orchestration core and the REST API.

Covers both workflow modes, agent state transitions, inter-agent message
passing, task delegation, JSON persistence round-trips, and the FastAPI
endpoints including live SSE log streaming.
"""

import asyncio
import time

from fastapi.testclient import TestClient

from src.main import app
from src.models import (
    AgentRole,
    AgentState,
    ArtifactKind,
    SprintStatus,
    TaskStatus,
    WorkflowMode,
)
from src.orchestrator import AgentManager, SprintStore

IDEA = "Build a task management app with user authentication and notifications"


def _run(coro):
    return asyncio.run(coro)


def _run_sprint(mode):
    async def scenario():
        manager = AgentManager(persist=False)
        return await manager.run(IDEA, mode)

    return _run(scenario())


# ---------------------------------------------------------------------------
# Sequential workflow
# ---------------------------------------------------------------------------


def test_sequential_workflow_completes_with_ordered_artifacts():
    sprint = _run_sprint(WorkflowMode.SEQUENTIAL)
    assert sprint.status is SprintStatus.COMPLETED
    assert sprint.error is None

    kinds = [a.kind for a in sprint.artifacts]
    assert kinds[0] is ArtifactKind.PRD
    assert ArtifactKind.USER_STORIES in kinds
    assert ArtifactKind.TASK_QUEUE in kinds
    assert kinds[kinds.index(ArtifactKind.TASK_QUEUE) + 1] is ArtifactKind.FOLDER_SCHEMA
    assert ArtifactKind.ERD in kinds
    assert ArtifactKind.API_CONTRACT in kinds
    assert ArtifactKind.SOURCE_CODE in kinds
    assert kinds[-1] is ArtifactKind.AUDIT_REPORT

    audit = [a for a in sprint.artifacts if a.kind is ArtifactKind.AUDIT_REPORT][0]
    assert audit.content["passed"] is True
    assert audit.content["score"] >= 60


def test_sequential_all_agents_reach_done_state():
    sprint = _run_sprint(WorkflowMode.SEQUENTIAL)
    assert sprint.agents == {role: AgentState.DONE for role in AgentRole}


def test_sequential_task_delegation_is_recorded():
    sprint = _run_sprint(WorkflowMode.SEQUENTIAL)
    assert len(sprint.tasks) == 4  # one execution task per agent role
    assert all(t.status is TaskStatus.COMPLETED for t in sprint.tasks)
    roles = {t.role for t in sprint.tasks}
    assert roles == {role for role in AgentRole}
    assert all(t.completed_at is not None for t in sprint.tasks)


def test_agent_state_transitions_are_recorded():
    sprint = _run_sprint(WorkflowMode.SEQUENTIAL)
    pm_events = [e for e in sprint.agent_events if e.role is AgentRole.PRODUCT_MANAGER]
    assert [e.to_state for e in pm_events] == [
        AgentState.READY,
        AgentState.WORKING,
        AgentState.DONE,
    ]
    # the first recorded transition departs from IDLE
    assert sprint.agent_events[0].from_state is AgentState.IDLE


def test_inter_agent_handoff_messages_flow_in_pipeline_order():
    sprint = _run_sprint(WorkflowMode.SEQUENTIAL)
    handoffs = {(m.sender, m.recipient) for m in sprint.messages if m.kind == "handoff"}
    assert (AgentRole.PRODUCT_MANAGER, AgentRole.ARCHITECT.value) in handoffs
    assert (AgentRole.ARCHITECT, AgentRole.DEVELOPER.value) in handoffs
    assert (AgentRole.DEVELOPER, AgentRole.QA_AUDITOR.value) in handoffs


def test_sequential_logs_cover_every_agent_role():
    sprint = _run_sprint(WorkflowMode.SEQUENTIAL)
    roles = {entry.role for entry in sprint.logs}
    assert {r.value for r in AgentRole} <= roles


def test_empty_idea_is_rejected():
    async def scenario():
        manager = AgentManager(persist=False)
        try:
            await manager.run("   ")
        except ValueError:
            return True
        return False

    assert _run(scenario()) is True


# ---------------------------------------------------------------------------
# Parallel workflow
# ---------------------------------------------------------------------------


def test_parallel_workflow_fans_out_sub_tasks():
    sprint = _run_sprint(WorkflowMode.PARALLEL)
    assert sprint.status is SprintStatus.COMPLETED

    code_artifacts = [a for a in sprint.artifacts if a.kind is ArtifactKind.SOURCE_CODE]
    audits = [a for a in sprint.artifacts if a.kind is ArtifactKind.AUDIT_REPORT]
    assert len(code_artifacts) >= 3  # core_api + detected features
    assert len(audits) == len(code_artifacts)
    assert all(a.content["passed"] for a in audits)


def test_parallel_still_runs_prd_and_architecture_once():
    sprint = _run_sprint(WorkflowMode.PARALLEL)
    prd = [a for a in sprint.artifacts if a.kind is ArtifactKind.PRD]
    erd = [a for a in sprint.artifacts if a.kind is ArtifactKind.ERD]
    assert len(prd) == 1
    assert len(erd) == 1


def test_parallel_all_delegated_tasks_complete():
    sprint = _run_sprint(WorkflowMode.PARALLEL)
    assert all(t.status is TaskStatus.COMPLETED for t in sprint.tasks)
    developer_tasks = [t for t in sprint.tasks if t.role is AgentRole.DEVELOPER]
    qa_tasks = [t for t in sprint.tasks if t.role is AgentRole.QA_AUDITOR]
    assert len(developer_tasks) >= 3
    assert len(qa_tasks) == len(developer_tasks)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_sprint_persists_and_reloads_from_disk(tmp_path):
    async def scenario():
        data_dir = tmp_path / "sprints"
        manager = AgentManager(data_dir=data_dir, persist=True)
        sprint = await manager.run(IDEA, WorkflowMode.SEQUENTIAL)
        assert (data_dir / f"{sprint.id}.json").exists()

        store = SprintStore(data_dir=data_dir)
        restored = store.get(sprint.id)
        assert restored is not None
        assert restored.status is SprintStatus.COMPLETED
        assert [a.kind for a in restored.artifacts] == [a.kind for a in sprint.artifacts]
        assert restored.agents == sprint.agents
        assert len(restored.logs) == len(sprint.logs)
        assert len(restored.messages) == len(sprint.messages)

    _run(scenario())


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------


def _wait_for_completion(client, sprint_id, timeout=30.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/sprints/{sprint_id}/status")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in ("completed", "failed"):
            return payload
        time.sleep(0.05)
    raise AssertionError(f"Sprint {sprint_id} did not finish within {timeout}s")


def test_api_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_api_create_status_and_artifacts_flow():
    with TestClient(app) as client:
        created = client.post(
            "/sprints/create",
            json={"idea": IDEA, "mode": "sequential"},
        )
        assert created.status_code == 201
        sprint_id = created.json()["sprint_id"]
        assert created.json()["status"] == "queued"

        status = _wait_for_completion(client, sprint_id)
        assert status["status"] == "completed"
        assert status["progress"] == 1.0
        agents = status["agents"]
        assert agents["product_manager"] == "done"
        assert agents["qa_auditor"] == "done"

        artifacts = client.get(f"/sprints/{sprint_id}/artifacts")
        assert artifacts.status_code == 200
        kinds = {a["kind"] for a in artifacts.json()["artifacts"]}
        assert {"prd", "erd", "source_code", "audit_report"} <= kinds


def test_api_validation_rejects_short_idea():
    with TestClient(app) as client:
        response = client.post("/sprints/create", json={"idea": "ab"})
        assert response.status_code == 422


def test_api_returns_404_for_unknown_sprint():
    with TestClient(app) as client:
        assert client.get("/sprints/nope/status").status_code == 404
        assert client.get("/sprints/nope/artifacts").status_code == 404


def test_api_lists_sprints():
    with TestClient(app) as client:
        client.post("/sprints/create", json={"idea": IDEA})
        response = client.get("/sprints")
        assert response.status_code == 200
        assert len(response.json()["sprints"]) >= 1
        first = response.json()["sprints"][0]
        assert first["sprint_id"]
        assert first["status"] in ("queued", "running", "completed", "failed")


def test_api_streams_live_agent_logs_over_sse():
    with TestClient(app) as client:
        created = client.post("/sprints/create", json={"idea": IDEA, "mode": "parallel"})
        sprint_id = created.json()["sprint_id"]
        _wait_for_completion(client, sprint_id)

        with client.stream("GET", f"/sprints/{sprint_id}/logs/stream") as stream:
            assert stream.status_code == 200
            body = "".join(stream.iter_text())

        assert "retry: 3000" in body
        assert 'data: {"timestamp"' in body
        assert '"type": "done"' in body
        assert '"status": "completed"' in body


def test_api_logs_endpoint_returns_json():
    with TestClient(app) as client:
        created = client.post("/sprints/create", json={"idea": IDEA})
        sprint_id = created.json()["sprint_id"]
        _wait_for_completion(client, sprint_id)
        response = client.get(f"/sprints/{sprint_id}/logs")
        assert response.status_code == 200
        logs = response.json()
        assert len(logs) > 0
        assert {"timestamp", "role", "level", "message"} <= set(logs[0])
