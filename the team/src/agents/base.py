"""Base classes and context plumbing shared by every agent.

The ``Reporter`` is the inter-agent message bus: it appends live log lines
and handoff messages to the active sprint, which the orchestrator persists
and the REST API streams to clients over SSE.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..models import AgentRole, ArtifactPayload, LogEntry, Message, Sprint, WorkflowMode


class Reporter:
    """Async bus that records agent logs and inter-agent messages."""

    async def log(self, sprint: Sprint, role: str, level: str, message: str) -> None:
        """Append one line of live agent output to the sprint."""
        sprint.logs.append(LogEntry(role=role, level=level, message=message))

    async def message(
        self,
        sprint: Sprint,
        sender: AgentRole,
        recipient: str,
        kind: str,
        content: str,
    ) -> None:
        """Send a message from one agent (or the orchestrator) to a recipient."""
        sprint.messages.append(
            Message(
                sprint_id=sprint.id,
                sender=sender,
                recipient=recipient,
                kind=kind,
                content=content,
            )
        )


@dataclass
class AgentContext:
    """Everything an agent needs to do its job in a single sprint."""

    sprint: Sprint
    workflow_mode: WorkflowMode
    reporter: Reporter
    task: Optional[Dict[str, Any]] = None


class BaseAgent(abc.ABC):
    """Abstract async agent.

    Subclasses implement ``_execute`` and declare ``role``/``display_name``.
    Agents are intentionally stateless: all state flows in through
    ``inputs`` and out through the returned artifact payloads, which lets the
    orchestrator run the same agent concurrently across parallel sub-tasks.
    """

    role: AgentRole = AgentRole.DEVELOPER
    display_name: str = "agent"

    async def run(self, context: AgentContext, inputs: Dict[str, Any]) -> List[ArtifactPayload]:
        """Run the agent against ``inputs`` and return validated payloads."""
        reporter, sprint = context.reporter, context.sprint
        await reporter.log(sprint, self.role.value, "info", f"{self.display_name} agent started")
        payloads = await self._execute(context, inputs)
        await reporter.log(sprint, self.role.value, "info", f"{self.display_name} agent finished")
        return payloads

    @abc.abstractmethod
    async def _execute(self, context: AgentContext, inputs: Dict[str, Any]) -> List[ArtifactPayload]:
        """Agent-specific execution.  Implement in each specialized role."""
        raise NotImplementedError
