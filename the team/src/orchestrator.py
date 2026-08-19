"""Async orchestration core.

``AgentManager`` owns the lifecycle of every sprint: it creates sprints,
delegates tasks to the specialized agents, records every agent state
transition, passes handoff messages between agents, and runs the team in one
of two workflow modes:

* **Sequential** — a linear pipeline: PM -> Architect -> Developer -> QA.
* **Parallel** — the PM's itemized task queue is fanned out; each developer
  sub-task (with its own QA pass) executes concurrently via ``asyncio.gather``.

``SprintStore`` keeps sprints in memory and optionally persists each one to
JSON on disk so runs survive restarts.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .agents import ArchitectAgent, DeveloperAgent, ProductManagerAgent, QAAuditorAgent
from .agents.base import AgentContext, Reporter
from .models import (
    AgentEvent,
    AgentRole,
    AgentState,
    Artifact,
    ArtifactKind,
    ExecutionTask,
    Message,
    Sprint,
    SprintStatus,
    TaskStatus,
    WorkflowMode,
    utcnow,
)

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sprints"


class SprintStore:
    """In-memory sprint registry with optional JSON persistence."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else None
        self._sprints: Dict[str, Sprint] = {}
        if self.data_dir:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self._load_existing()

    def _load_existing(self) -> None:
        for path in sorted(self.data_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sprint = Sprint.model_validate(data)
                self._sprints[sprint.id] = sprint
            except Exception:
                # Skip corrupt or partial files; they will simply be missing.
                continue

    def create(self, idea: str, mode: WorkflowMode) -> Sprint:
        sprint = Sprint(idea=idea, mode=mode)
        self._sprints[sprint.id] = sprint
        return sprint

    def get(self, sprint_id: str) -> Optional[Sprint]:
        return self._sprints.get(sprint_id)

    def all(self) -> List[Sprint]:
        return sorted(self._sprints.values(), key=lambda s: s.created_at)

    async def persist(self, sprint: Sprint) -> None:
        if self.data_dir is None:
            return
        payload = sprint.model_dump(mode="json")
        await asyncio.to_thread(self._write, sprint.id, payload)

    def _write(self, sprint_id: str, payload: Dict[str, Any]) -> None:
        path = self.data_dir / f"{sprint_id}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


class AgentManager:
    """Coordinates the agent team across a sprint lifecycle."""

    def __init__(
        self,
        store: Optional[SprintStore] = None,
        data_dir: Optional[Path] = None,
        persist: bool = True,
        agent_timeout: float = 120.0,
    ) -> None:
        self.store = store or SprintStore(data_dir if persist else None)
        self.persist = persist
        self.agent_timeout = agent_timeout
        self.reporter = Reporter()
        self.agents = {
            AgentRole.PRODUCT_MANAGER: ProductManagerAgent(),
            AgentRole.ARCHITECT: ArchitectAgent(),
            AgentRole.DEVELOPER: DeveloperAgent(),
            AgentRole.QA_AUDITOR: QAAuditorAgent(),
        }

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    async def run(self, idea: str, mode: WorkflowMode = WorkflowMode.SEQUENTIAL) -> Sprint:
        """Create a sprint and await its full execution."""
        sprint = await self._create_sprint(idea, mode)
        await self._execute(sprint)
        return sprint

    async def start(self, idea: str, mode: WorkflowMode = WorkflowMode.SEQUENTIAL) -> Sprint:
        """Create a sprint and kick off background execution (non-blocking)."""
        sprint = await self._create_sprint(idea, mode)
        asyncio.create_task(self._execute(sprint))
        return sprint

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    async def _create_sprint(self, idea: str, mode: WorkflowMode) -> Sprint:
        if not isinstance(idea, str) or not idea.strip():
            raise ValueError("Sprint idea must be a non-empty string.")
        sprint = self.store.create(idea.strip(), mode)
        await self.reporter.log(sprint, "orchestrator", "info", f"Sprint {sprint.id} created in {mode.value} mode")
        return sprint

    async def _execute(self, sprint: Sprint) -> None:
        sprint.status = SprintStatus.RUNNING
        await self.reporter.log(sprint, "orchestrator", "info", f"Sprint {sprint.id} started")
        try:
            if sprint.mode is WorkflowMode.SEQUENTIAL:
                await self._run_sequential(sprint)
            else:
                await self._run_parallel(sprint)
            sprint.status = SprintStatus.COMPLETED
            sprint.completed_at = utcnow()
            await self.reporter.log(sprint, "orchestrator", "info", f"Sprint {sprint.id} completed successfully")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - sprint failures are recorded, not raised
            sprint.status = SprintStatus.FAILED
            sprint.completed_at = utcnow()
            sprint.error = str(exc)
            await self.reporter.log(sprint, "orchestrator", "error", f"Sprint {sprint.id} failed: {exc}")
        await self.store.persist(sprint)

    def _transition(self, sprint: Sprint, role: AgentRole, to_state: AgentState) -> None:
        event = AgentEvent(role=role, from_state=sprint.agents[role], to_state=to_state)
        sprint.agents[role] = to_state
        sprint.agent_events.append(event)

    def _handoff(self, sprint: Sprint, sender: AgentRole, recipient: AgentRole, summary: str) -> None:
        sprint.messages.append(
            Message(
                sprint_id=sprint.id,
                sender=sender,
                recipient=recipient.value,
                kind="handoff",
                content=summary,
            )
        )

    async def _run_agent(
        self,
        sprint: Sprint,
        agent: Any,
        inputs: Dict[str, Any],
        description: str,
    ) -> List[Artifact]:
        """Delegate one task to an agent, tracking state transitions and artifacts."""
        role = agent.role
        execution = ExecutionTask(description=description, role=role)
        sprint.tasks.append(execution)

        await self.reporter.log(
            sprint, "orchestrator", "info", f"Delegating task to {agent.display_name}: {description}"
        )
        self._transition(sprint, role, AgentState.READY)
        self._transition(sprint, role, AgentState.WORKING)
        execution.status = TaskStatus.IN_PROGRESS

        context = AgentContext(sprint=sprint, workflow_mode=sprint.mode, reporter=self.reporter)
        try:
            payloads = await asyncio.wait_for(agent.run(context, inputs), timeout=self.agent_timeout)
        except Exception as exc:
            execution.status = TaskStatus.FAILED
            execution.completed_at = utcnow()
            self._transition(sprint, role, AgentState.BLOCKED)
            await self.reporter.log(sprint, role.value, "error", f"Agent failed: {exc}")
            raise

        execution.status = TaskStatus.COMPLETED
        execution.completed_at = utcnow()
        self._transition(sprint, role, AgentState.DONE)
        artifacts = [
            Artifact(sprint_id=sprint.id, producer=role, kind=p.kind, title=p.title, content=p.content)
            for p in payloads
        ]
        sprint.artifacts.extend(artifacts)
        await self.reporter.log(sprint, role.value, "info", f"Produced {len(artifacts)} artifact(s)")
        await self.store.persist(sprint)
        return artifacts

    @staticmethod
    def _artifact_by_kind(artifacts: List[Artifact], kind: ArtifactKind) -> Artifact:
        for artifact in artifacts:
            if artifact.kind is kind:
                return artifact
        raise ValueError(f"No artifact of kind {kind.value} produced")

    # ------------------------------------------------------------------
    # sequential workflow (linear pipeline)
    # ------------------------------------------------------------------

    async def _run_sequential(self, sprint: Sprint) -> None:
        pm_artifacts = await self._run_agent(
            sprint,
            self.agents[AgentRole.PRODUCT_MANAGER],
            {"idea": sprint.idea},
            description="Produce PRD, user stories, and itemized task queue from the idea",
        )
        prd = self._artifact_by_kind(pm_artifacts, ArtifactKind.PRD)
        self._handoff(sprint, AgentRole.PRODUCT_MANAGER, AgentRole.ARCHITECT, f"PRD '{prd.title}' delivered")

        arch_artifacts = await self._run_agent(
            sprint,
            self.agents[AgentRole.ARCHITECT],
            {"prd": prd.content},
            description="Translate the PRD into folder schema, ERD, and REST API contract",
        )
        schema_bundle = {a.kind.value: a.content for a in arch_artifacts}
        self._handoff(
            sprint,
            AgentRole.ARCHITECT,
            AgentRole.DEVELOPER,
            f"Architecture ready: {schema_bundle[ArtifactKind.ERD.value]['overview']}",
        )

        dev_artifacts = await self._run_agent(
            sprint,
            self.agents[AgentRole.DEVELOPER],
            {"prd": prd.content, "schema": schema_bundle},
            description="Generate runnable source code from the architecture",
        )
        code = self._artifact_by_kind(dev_artifacts, ArtifactKind.SOURCE_CODE)
        self._handoff(
            sprint,
            AgentRole.DEVELOPER,
            AgentRole.QA_AUDITOR,
            f"{len(code.content.get('files', {}))} source files ready for audit",
        )

        await self._run_agent(
            sprint,
            self.agents[AgentRole.QA_AUDITOR],
            {"code": code.content, "schema": schema_bundle},
            description="Audit generated code for syntax errors, edge cases, and security",
        )

    # ------------------------------------------------------------------
    # parallel workflow (fan-out of the itemized task queue)
    # ------------------------------------------------------------------

    async def _run_parallel(self, sprint: Sprint) -> None:
        pm_artifacts = await self._run_agent(
            sprint,
            self.agents[AgentRole.PRODUCT_MANAGER],
            {"idea": sprint.idea},
            description="Produce PRD, user stories, and itemized task queue from the idea",
        )
        prd = self._artifact_by_kind(pm_artifacts, ArtifactKind.PRD)
        queue = self._artifact_by_kind(pm_artifacts, ArtifactKind.TASK_QUEUE)
        self._handoff(
            sprint,
            AgentRole.PRODUCT_MANAGER,
            AgentRole.ARCHITECT,
            f"PRD '{prd.title}' with {len(queue.content.get('tasks', []))} queued tasks",
        )

        arch_artifacts = await self._run_agent(
            sprint,
            self.agents[AgentRole.ARCHITECT],
            {"prd": prd.content},
            description="Translate the PRD into folder schema, ERD, and REST API contract",
        )
        schema_bundle = {a.kind.value: a.content for a in arch_artifacts}

        dev_tasks = [t for t in queue.content.get("tasks", []) if t.get("role") == AgentRole.DEVELOPER.value]
        await self.reporter.log(
            sprint,
            "orchestrator",
            "info",
            f"Fanning out {len(dev_tasks)} developer sub-task(s) in parallel",
        )
        results = await asyncio.gather(
            *[self._run_sub_pipeline(sprint, prd.content, schema_bundle, task) for task in dev_tasks],
            return_exceptions=True,
        )
        failures = [result for result in results if isinstance(result, Exception)]
        if failures:
            raise failures[0]

    async def _run_sub_pipeline(self, sprint: Sprint, prd_content: Dict[str, Any], schema_bundle: Dict[str, Any], task: Dict[str, Any]) -> None:
        """One developer -> QA pipeline for a single itemized task."""
        self._handoff(
            sprint,
            AgentRole.ARCHITECT,
            AgentRole.DEVELOPER,
            f"Schema for task {task.get('id', '?')}: {task.get('title', '')}",
        )
        dev_artifacts = await self._run_agent(
            sprint,
            self.agents[AgentRole.DEVELOPER],
            {"prd": prd_content, "schema": schema_bundle, "task": task},
            description=f"Implement: {task.get('title', 'unnamed task')}",
        )
        code = self._artifact_by_kind(dev_artifacts, ArtifactKind.SOURCE_CODE)
        self._handoff(sprint, AgentRole.DEVELOPER, AgentRole.QA_AUDITOR, f"Code for task {task.get('id', '?')} ready for audit")
        await self._run_agent(
            sprint,
            self.agents[AgentRole.QA_AUDITOR],
            {"code": code.content, "schema": schema_bundle, "task": task},
            description=f"Audit: {task.get('title', 'unnamed task')}",
        )
