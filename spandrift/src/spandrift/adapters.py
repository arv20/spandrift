"""Drop-in framework adapters and tracing utilities.

Provides:
1. Clean decorators: @trace_agent, @trace_tool, @trace_llm
2. **Experimental** LangGraph / LangChain callback handler: SpandriftCallbackHandler
   (not tested against real LangChain runs — use at your own risk in v0.1.x)
"""

from __future__ import annotations

import functools
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Callable, ParamSpec, TypeVar

from spandrift.models import Span, SpanKind
from spandrift.profiler import (
    collect_trace,
    get_current_span,
    mark_first_token,
    profile_agent,
    profile_tool,
    span_scope,
)

P = ParamSpec("P")
T = TypeVar("T")

# Convenient aliases for raw asyncio workflows
trace_agent = profile_agent
trace_tool = profile_tool


def trace_llm(
    name: str = "llm_call",
    model: str = "gpt-4o",
    provider: str = "openai",
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to profile raw LLM function invocations."""

    def decorator(fn: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            async with span_scope(
                name=name,
                kind=SpanKind.LLM,
                model=model,
                provider=provider,
                operation="chat",
            ):
                return await fn(*args, **kwargs)  # type: ignore[no-any-return]

        return wrapper  # type: ignore[return-value]

    return decorator


# ---------------------------------------------------------------------------
# LangGraph / LangChain Callback Handler
# ---------------------------------------------------------------------------

class SpandriftCallbackHandler:
    """Async & sync callback handler compatible with LangChain and LangGraph.

    .. warning:: Experimental
        This handler has not been tested against real LangChain/LangGraph runs.
        It is provided as a starting point for integration. LangChain already
        has first-party observability via LangSmith — prefer that if available.
    """

    def __init__(self, agent_name: str | None = None) -> None:
        self.agent_name = agent_name
        self._active_scopes: dict[str, Any] = {}

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Any | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        name = serialized.get("name") or (tags[0] if tags else "Chain")
        # In an async/sync callback, we record metadata for trace collection
        self._active_scopes[str(run_id)] = {
            "name": name,
            "kind": SpanKind.AGENT if not parent_run_id else SpanKind.CHAIN,
            "start_time": time.time_ns(),
            "inputs": inputs,
        }

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: Any,
        parent_run_id: Any | None = None,
        **kwargs: Any,
    ) -> None:
        model = serialized.get("name") or kwargs.get("invocation_params", {}).get("model", "llm")
        self._active_scopes[str(run_id)] = {
            "name": f"chat {model}",
            "kind": SpanKind.LLM,
            "model": model,
            "start_time": time.time_ns(),
            "first_token": False,
        }

    def on_llm_new_token(self, token: str, *, run_id: Any, **kwargs: Any) -> None:
        scope = self._active_scopes.get(str(run_id))
        if scope and not scope.get("first_token"):
            scope["first_token"] = True
            mark_first_token()

    def on_llm_end(self, response: Any, *, run_id: Any, **kwargs: Any) -> None:
        self._active_scopes.pop(str(run_id), None)

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        name = serialized.get("name") or "tool"
        self._active_scopes[str(run_id)] = {
            "name": name,
            "kind": SpanKind.TOOL,
            "start_time": time.time_ns(),
        }

    def on_tool_end(self, output: str, *, run_id: Any, **kwargs: Any) -> None:
        self._active_scopes.pop(str(run_id), None)
