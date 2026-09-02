"""Internal span schema — one normalized type for all sources.

Fields map directly onto OTel GenAI semantic conventions. This is a typed
in-memory projection, not a new wire format.
"""

from __future__ import annotations

import dataclasses
import enum
from typing import Any


class SpanKind(enum.Enum):
    """Mirrors OTel GenAI operation types, not OTel SpanKind."""

    AGENT = "agent"
    LLM = "llm"
    TOOL = "tool"
    CHAIN = "chain"
    INTERNAL = "internal"


@dataclasses.dataclass(frozen=True, slots=True)
class Span:
    """A single normalized span from any source (OTLP, OpenInference, profiler).

    Frozen so spans are safe to share across tasks and store in sets.
    Slots for memory efficiency when holding thousands of spans.
    """

    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    kind: SpanKind
    start_ns: int  # nanoseconds since epoch
    end_ns: int  # nanoseconds since epoch

    # Agent / model metadata — None when not applicable
    agent_name: str | None = None
    model: str | None = None
    provider: str | None = None
    operation: str | None = None  # "chat", "invoke_agent", "execute_tool", etc.

    # Token usage — 0 when not an LLM span
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    # Cost in USD — None until enriched by cost_engine
    cost: float | None = None

    # SHA-256 prefix of serialized input, for duplicate / retry detection
    input_hash: str | None = None

    # Raw serialized input string for semantic / token-overlap similarity analysis
    input_value: str | None = None

    # Time-to-first-token: absolute nanosecond timestamp of the first chunk.
    # Populated from gen_ai.response.time_to_first_chunk during ingest, or
    # via mark_first_token() in the profiler path for streaming code.
    # None when TTFT is not available (non-streaming calls, uninstrumented).
    first_token_ns: int | None = None

    # Status
    status_code: int = 0  # 0=UNSET, 1=OK, 2=ERROR
    status_message: str | None = None

    # Anything we don't normalize — available for custom analysis
    attributes: dict[str, Any] = dataclasses.field(default_factory=dict)

    # OTLP resource and instrumentation-scope metadata. These remain separate
    # from span attributes so equal keys from different OTLP namespaces do not
    # overwrite one another.
    resource_attributes: dict[str, Any] = dataclasses.field(default_factory=dict)
    scope_name: str | None = None
    scope_version: str | None = None
    scope_attributes: dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        """Wall-clock duration in milliseconds."""
        return (self.end_ns - self.start_ns) / 1_000_000

    @property
    def duration_s(self) -> float:
        """Wall-clock duration in seconds."""
        return (self.end_ns - self.start_ns) / 1_000_000_000

    @property
    def ttft_ms(self) -> float | None:
        """Time-to-first-token in milliseconds, or None if not recorded.

        This is distinct from duration_ms: TTFT measures start → first chunk,
        while duration measures start → end. For non-streaming calls or spans
        where TTFT wasn't captured, returns None.
        """
        if self.first_token_ns is None:
            return None
        return (self.first_token_ns - self.start_ns) / 1_000_000

    def with_cost(self, cost: float) -> Span:
        """Return a copy with cost filled in."""
        return dataclasses.replace(self, cost=cost)
