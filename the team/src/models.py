"""Core domain models for the multi-agent development system.

Every structured input and output produced by the agent team is validated
through the Pydantic models defined here.  Agent artifacts are wrapped in
``Artifact`` records, agent lifecycle events in ``AgentEvent`` records, and
inter-agent handoffs in ``Message`` records so the orchestrator can persist
and replay a whole sprint.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp used across all records."""
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    """Generate a compact, collision-resistant record identifier."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class AgentRole(str, Enum):
    """The four specialized roles that make up the agent team."""

    PRODUCT_MANAGER = "product_manager"
    ARCHITECT = "architect"
    DEVELOPER = "developer"
    QA_AUDITOR = "qa_auditor"


class AgentState(str, Enum):
    """Lifecycle states an agent moves through during a sprint."""

    IDLE = "idle"
    READY = "ready"
    WORKING = "working"
    BLOCKED = "blocked"
    DONE = "done"
    FAILED = "failed"


class TaskStatus(str, Enum):
    """Lifecycle states of an execution task delegated to an agent."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowMode(str, Enum):
    """How the orchestrator runs a sprint."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class SprintStatus(str, Enum):
    """Overall lifecycle states of a sprint."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ArtifactKind(str, Enum):
    """Kinds of artifacts an agent can produce."""

    PRD = "prd"
    USER_STORIES = "user_stories"
    TASK_QUEUE = "task_queue"
    FOLDER_SCHEMA = "folder_schema"
    ERD = "erd"
    API_CONTRACT = "api_contract"
    SOURCE_CODE = "source_code"
    AUDIT_REPORT = "audit_report"


class Severity(str, Enum):
    """Severity levels assigned to QA audit findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Sprint-level records
# ---------------------------------------------------------------------------


class LogEntry(BaseModel):
    """A single line of live agent output."""

    timestamp: datetime = Field(default_factory=utcnow)
    role: str = "orchestrator"
    level: str = "info"
    message: str = ""


class AgentEvent(BaseModel):
    """A recorded agent state transition (e.g. ready -> working)."""

    role: AgentRole
    from_state: AgentState
    to_state: AgentState
    at: datetime = Field(default_factory=utcnow)


class Message(BaseModel):
    """An inter-agent message passed over the orchestrator bus."""

    id: str = Field(default_factory=lambda: new_id("msg"))
    sprint_id: str = ""
    sender: AgentRole
    recipient: str
    kind: str = "info"
    content: str = ""
    timestamp: datetime = Field(default_factory=utcnow)


class ExecutionTask(BaseModel):
    """A task delegated to an agent during a sprint."""

    id: str = Field(default_factory=lambda: new_id("task"))
    description: str = ""
    role: AgentRole
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=utcnow)
    completed_at: Optional[datetime] = None


class Artifact(BaseModel):
    """A validated piece of output produced by an agent."""

    id: str = Field(default_factory=lambda: new_id("art"))
    sprint_id: str = ""
    kind: ArtifactKind
    title: str = ""
    producer: AgentRole
    content: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


class ArtifactPayload(BaseModel):
    """An agent's raw output before it is wrapped into an Artifact record."""

    kind: ArtifactKind
    title: str = ""
    content: Dict[str, Any] = Field(default_factory=dict)


class Sprint(BaseModel):
    """The aggregate root: one sprint, one idea, one run of the agent team."""

    id: str = Field(default_factory=lambda: new_id("spr"))
    idea: str
    mode: WorkflowMode = WorkflowMode.SEQUENTIAL
    status: SprintStatus = SprintStatus.QUEUED
    error: Optional[str] = None
    agents: Dict[AgentRole, AgentState] = Field(
        default_factory=lambda: {role: AgentState.IDLE for role in AgentRole}
    )
    tasks: List[ExecutionTask] = Field(default_factory=list)
    artifacts: List[Artifact] = Field(default_factory=list)
    messages: List[Message] = Field(default_factory=list)
    logs: List[LogEntry] = Field(default_factory=list)
    agent_events: List[AgentEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    completed_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Structured agent outputs
# ---------------------------------------------------------------------------


class Feature(BaseModel):
    """A single feature captured inside a PRD."""

    key: str
    name: str
    description: str = ""
    priority: str = "P1"


class PRDContent(BaseModel):
    """Structured Product Requirements Document produced by the PM agent."""

    project_name: str
    overview: str = ""
    goals: List[str] = Field(default_factory=list)
    target_users: List[str] = Field(default_factory=list)
    features: List[Feature] = Field(default_factory=list)
    non_functional_requirements: List[str] = Field(default_factory=list)
    success_metrics: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class UserStory(BaseModel):
    """An agile user story in the standard As-a/I-want/So-that form."""

    id: str
    as_a: str
    i_want: str
    so_that: str
    priority: str = "P1"


class UserStoriesContent(BaseModel):
    """The collection of user stories produced by the PM agent."""

    stories: List[UserStory] = Field(default_factory=list)


class TaskQueueItem(BaseModel):
    """A single itemized task from the PM agent's task queue."""

    id: str
    title: str
    description: str = ""
    role: AgentRole
    feature_key: Optional[str] = None
    acceptance_criteria: List[str] = Field(default_factory=list)


class TaskQueueContent(BaseModel):
    """The itemized task queue produced by the PM agent."""

    tasks: List[TaskQueueItem] = Field(default_factory=list)


class ERDField(BaseModel):
    """A single column of an ERD entity."""

    name: str
    type: str
    constraints: List[str] = Field(default_factory=list)


class EntityRelation(BaseModel):
    """A relationship between two ERD entities."""

    type: str = "many-to-one"
    target: str
    on_delete: str = "cascade"


class Entity(BaseModel):
    """An ERD entity (database table) with fields and relations."""

    name: str
    table: str
    description: str = ""
    fields: List[ERDField] = Field(default_factory=list)
    relations: List[EntityRelation] = Field(default_factory=list)


class ERDContent(BaseModel):
    """Entity-Relationship model produced by the architect agent."""

    overview: str = ""
    assumptions: List[str] = Field(default_factory=list)
    entities: List[Entity] = Field(default_factory=list)


class FolderEntry(BaseModel):
    """One entry of the proposed project folder schema."""

    path: str
    type: str = "file"  # "dir" | "file"
    purpose: str = ""


class FolderSchemaContent(BaseModel):
    """The project folder schema produced by the architect agent."""

    root: str
    tree: str = ""
    structure: List[FolderEntry] = Field(default_factory=list)


class Endpoint(BaseModel):
    """A single REST endpoint in the API contract."""

    method: str
    path: str
    summary: str = ""
    request_body: Optional[Dict[str, Any]] = None
    responses: List[str] = Field(default_factory=list)


class APIContractContent(BaseModel):
    """The REST API contract produced by the architect agent."""

    base_path: str = "/api/v1"
    auth: str = "none"
    endpoints: List[Endpoint] = Field(default_factory=list)


class CodeContent(BaseModel):
    """Runnable source files produced by the developer agent."""

    project_name: str = "generated-project"
    files: Dict[str, str] = Field(default_factory=dict)
    feature_keys: List[str] = Field(default_factory=list)
    summary: str = ""


class Finding(BaseModel):
    """A single QA audit finding."""

    severity: Severity
    category: str
    file: str
    line: Optional[int] = None
    message: str = ""
    recommendation: str = ""


class AuditReportContent(BaseModel):
    """The QA audit report produced by the QA auditor agent."""

    summary: str = ""
    score: int = 100
    passed: bool = True
    files_audited: List[str] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)
    checks_run: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# REST API request / response models
# ---------------------------------------------------------------------------


class SprintCreateRequest(BaseModel):
    """Payload for POST /sprints/create."""

    idea: str = Field(..., min_length=3, max_length=2000, description="High-level product idea to develop")
    mode: WorkflowMode = WorkflowMode.SEQUENTIAL


class SprintCreateResponse(BaseModel):
    """Response for POST /sprints/create."""

    sprint_id: str
    status: SprintStatus
    mode: WorkflowMode
    idea: str
    created_at: datetime


class SprintStatusResponse(BaseModel):
    """Response for GET /sprints/{id}/status."""

    sprint_id: str
    status: SprintStatus
    mode: WorkflowMode
    idea: str
    error: Optional[str] = None
    progress: float = 0.0
    agents: Dict[AgentRole, AgentState] = Field(default_factory=dict)
    tasks: List[ExecutionTask] = Field(default_factory=list)
    created_at: datetime
    completed_at: Optional[datetime] = None


class SprintArtifactsResponse(BaseModel):
    """Response for GET /sprints/{id}/artifacts."""

    sprint_id: str
    artifacts: List[Artifact] = Field(default_factory=list)


class SprintSummary(BaseModel):
    """Lightweight record used by the sprint listing endpoint."""

    sprint_id: str
    idea: str
    mode: WorkflowMode
    status: SprintStatus
    created_at: datetime


class SprintListResponse(BaseModel):
    """Response for GET /sprints."""

    sprints: List[SprintSummary] = Field(default_factory=list)
