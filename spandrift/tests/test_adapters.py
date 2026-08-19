"""Tests for adapters.py (LangGraph callback and trace decorators)."""

from __future__ import annotations

import pytest

from spandrift.adapters import SpandriftCallbackHandler, trace_agent, trace_llm, trace_tool
from spandrift.profiler import collect_trace


@pytest.mark.asyncio
async def test_trace_decorators():
    async with collect_trace() as spans:

        @trace_tool(name="calculator")
        async def calc(expr: str) -> str:
            return "42"

        @trace_llm(name="chat gpt-4o", model="gpt-4o", provider="openai")
        async def call_llm(prompt: str) -> str:
            return "response"

        @trace_agent(name="MathAgent")
        async def solve(query: str) -> str:
            await calc(query)
            return await call_llm(query)

        await solve("2+2")

    assert len(spans) == 3
    names = {s.name for s in spans}
    assert "MathAgent" in names
    assert "calculator" in names
    assert "chat gpt-4o" in names


def test_langgraph_callback_handler():
    handler = SpandriftCallbackHandler(agent_name="TestAgent")

    # Simulate chain start
    handler.on_chain_start({"name": "AgentStep"}, {"input": "test"}, run_id="run_1")
    # Simulate LLM start
    handler.on_llm_start({"name": "gpt-4o"}, ["hello"], run_id="run_2", parent_run_id="run_1")
    # Simulate first token
    handler.on_llm_new_token("chunk1", run_id="run_2")
    # Simulate LLM end
    handler.on_llm_end({}, run_id="run_2")
    # Simulate tool start and end
    handler.on_tool_start({"name": "web_search"}, "query", run_id="run_3")
    handler.on_tool_end("result", run_id="run_3")
