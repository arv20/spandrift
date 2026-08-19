"""Lightweight profiling decorator for agent orchestration code.

Use @profile_agent(name="...") to wrap async agent functions that aren't
already instrumented by OTel / smolagents / Pydantic AI. Emits spans in the
same shape as ingest.py normalizes, so profiled and ingested spans merge
seamlessly.

Concurrent span attribution
----------------------------
The critical invariant: when two sub-agents run concurrently (via
asyncio.gather or TaskGroup), each agent's spans must reference the correct
parent — not the other agent's span.

We use contextvars.ContextVar for the "current span" pointer. This works
because asyncio.create_task() (and therefore gather/TaskGroup) copies the
calling task's context via contextvars.copy_context(). Each new Task gets an
independent snapshot backed by a HAMT (Hash Array Mapped Trie), so
ContextVar.set() in Task A never affects Task B. The copy is O(1) — it
increments the HAMT root's refcount, not cloning entries.

Within a single task, sequential await calls share the same context (no copy),
which is exactly what we want: a decorator that calls await sub_agent()
correctly sees the outer span as the parent.

We use token-based reset (ContextVar.set returns a Token, reset(token)
restores the previous value) so that when a child span ends, the parent span
becomes "current" again within that task's context. This mirrors the OTel
Python SDK's attach/detach pattern.
"""

from __future__ import annotations

import asyncio
import contextvars
import dataclasses
import functools
import hashlib
import json
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Callable, ParamSpec, TypeVar

from spandrift.models import Span, SpanKind

P = ParamSpec("P")
T = TypeVar("T")

# --- Context variables (per-task isolated via asyncio's copy semantics) ---

_current_span: contextvars.ContextVar[Span | None] = contextvars.ContextVar(
    "spandrift_current_span", default=None
)

# The collector list is shared by reference across tasks within a trace.
# asyncio tasks are cooperatively scheduled on a single thread — there is no
# preemption inside a synchronous statement like list.append(), so concurrent
# appends from different tasks are safe without a lock. (This holds regardless
# of the GIL; the real guarantee is cooperative scheduling.)
_span_collector: contextvars.ContextVar[list[Span] | None] = contextvars.ContextVar(
    "spandrift_span_collector", default=None
)

# Per-span first-token timestamp, set by mark_first_token() during streaming.
# Token-based save/restore in span_scope ensures nesting is correct.
_first_token_ns: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "spandrift_first_token_ns", default=None
)


def get_current_span() -> Span | None:
    """Return the currently active span for this task, or None."""
    return _current_span.get()


def mark_first_token() -> None:
    """Record the current time as the first-token timestamp for the active span.

    Call this from streaming LLM code when the first chunk arrives::

        async for chunk in model.stream(prompt):
            if first_chunk:
                mark_first_token()
            ...

    The timestamp is consumed by the enclosing span_scope and stored as
    ``Span.first_token_ns``. Only the first call per span takes effect.
    """
    if _first_token_ns.get() is None:
        _first_token_ns.set(time.time_ns())


@asynccontextmanager
async def span_scope(
    name: str,
    kind: SpanKind,
    *,
    agent_name: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    operation: str | None = None,
    input_hash: str | None = None,
    input_value: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    attributes: dict[str, Any] | None = None,
) -> AsyncIterator[Span]:
    """Context manager that creates a span, sets it as current, and cleans up."""
    parent = _current_span.get()
    trace_id = parent.trace_id if parent else uuid.uuid4().hex
    span = Span(
        trace_id=trace_id,
        span_id=uuid.uuid4().hex[:16],
        parent_span_id=parent.span_id if parent else None,
        name=name,
        kind=kind,
        start_ns=time.time_ns(),
        end_ns=0,
        agent_name=agent_name,
        model=model,
        provider=provider,
        operation=operation,
        input_hash=input_hash,
        input_value=input_value,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        attributes=attributes or {},
    )
    span_token = _current_span.set(span)
    ft_token = _first_token_ns.set(None)
    try:
        yield span
    finally:
        first_token = _first_token_ns.get()
        completed = dataclasses.replace(
            span, end_ns=time.time_ns(), first_token_ns=first_token
        )
        collector = _span_collector.get()
        if collector is not None:
            collector.append(completed)
        _first_token_ns.reset(ft_token)
        _current_span.reset(span_token)


@asynccontextmanager
async def collect_trace() -> AsyncIterator[list[Span]]:
    """Top-level context manager that collects all spans emitted during a trace."""
    collector: list[Span] = []
    token = _span_collector.set(collector)
    try:
        yield collector
    finally:
        _span_collector.reset(token)


def _serialize_input(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """Best-effort JSON serialization of function arguments for hashing."""
    try:
        return json.dumps({"args": args, "kwargs": kwargs}, default=str, sort_keys=True)
    except (TypeError, ValueError):
        return str((args, kwargs))


def _hash_input(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """SHA-256 prefix of serialized input, for duplicate/retry detection."""
    serialized = _serialize_input(args, kwargs)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def profile_agent(name: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator that wraps an async agent function in a profiling span."""

    def decorator(fn: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            raw_input = _serialize_input(args, kwargs)
            input_h = hashlib.sha256(raw_input.encode()).hexdigest()[:16]
            async with span_scope(
                name=name,
                kind=SpanKind.AGENT,
                agent_name=name,
                operation="invoke_agent",
                input_hash=input_h,
                input_value=raw_input,
            ):
                result = await fn(*args, **kwargs)
                return result

        return wrapper  # type: ignore[return-value]

    return decorator


def profile_tool(name: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator that wraps an async tool function in a profiling span."""

    def decorator(fn: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            raw_input = _serialize_input(args, kwargs)
            input_h = hashlib.sha256(raw_input.encode()).hexdigest()[:16]
            async with span_scope(
                name=name,
                kind=SpanKind.TOOL,
                operation="execute_tool",
                input_hash=input_h,
                input_value=raw_input,
            ):
                result = await fn(*args, **kwargs)
                return result

        return wrapper  # type: ignore[return-value]

    return decorator
