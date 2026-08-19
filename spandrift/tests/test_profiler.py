"""Tests for concurrent span attribution in profiler.py.

These are the most important tests in the project. The profiler's correctness
under concurrency depends on ContextVar's per-task copy semantics — these tests
verify that by forcing interleaving and checking parent/child relationships.
"""

from __future__ import annotations

import asyncio

import pytest

from spandrift.models import Span, SpanKind
from spandrift.profiler import (
    _current_span,
    _span_collector,
    collect_trace,
    profile_agent,
    profile_tool,
    span_scope,
)


@pytest.mark.asyncio
async def test_concurrent_span_attribution_no_cross_contamination():
    """Two agents launched via gather must not cross-contaminate parent spans.

    This is the critical test: if span attribution used a shared variable
    instead of ContextVar, the asyncio.sleep() calls would cause agent_a's
    LLM span to see agent_b's span as its parent (because agent_b would
    overwrite the shared variable while agent_a sleeps).
    """
    async with collect_trace() as spans:

        @profile_agent(name="AgentA")
        async def agent_a() -> str:
            await asyncio.sleep(0.02)  # force interleaving: B starts while A sleeps
            async with span_scope("llm_call_a", SpanKind.LLM, model="gpt-4o"):
                await asyncio.sleep(0.01)
            return "a"

        @profile_agent(name="AgentB")
        async def agent_b() -> str:
            async with span_scope("llm_call_b", SpanKind.LLM, model="claude-3"):
                await asyncio.sleep(0.02)  # overlaps with agent_a's LLM call
            return "b"

        async with span_scope("orchestrator", SpanKind.AGENT, agent_name="Orchestrator"):
            await asyncio.gather(agent_a(), agent_b())

    # Build lookup
    by_name: dict[str, Span] = {}
    for s in spans:
        by_name[s.name] = s

    assert "AgentA" in by_name
    assert "AgentB" in by_name
    assert "llm_call_a" in by_name
    assert "llm_call_b" in by_name
    assert "orchestrator" in by_name

    # LLM call A's parent must be AgentA, not AgentB or orchestrator
    assert by_name["llm_call_a"].parent_span_id == by_name["AgentA"].span_id

    # LLM call B's parent must be AgentB, not AgentA or orchestrator
    assert by_name["llm_call_b"].parent_span_id == by_name["AgentB"].span_id

    # Both agents' parent must be the orchestrator
    assert by_name["AgentA"].parent_span_id == by_name["orchestrator"].span_id
    assert by_name["AgentB"].parent_span_id == by_name["orchestrator"].span_id


@pytest.mark.asyncio
async def test_concurrent_with_taskgroup():
    """Same test but using TaskGroup instead of gather."""
    async with collect_trace() as spans:

        @profile_agent(name="Worker1")
        async def worker1() -> None:
            await asyncio.sleep(0.01)
            async with span_scope("tool_1", SpanKind.TOOL):
                await asyncio.sleep(0.01)

        @profile_agent(name="Worker2")
        async def worker2() -> None:
            async with span_scope("tool_2", SpanKind.TOOL):
                await asyncio.sleep(0.02)

        async with span_scope("root", SpanKind.AGENT, agent_name="Root"):
            async with asyncio.TaskGroup() as tg:
                tg.create_task(worker1())
                tg.create_task(worker2())

    by_name = {s.name: s for s in spans}

    assert by_name["tool_1"].parent_span_id == by_name["Worker1"].span_id
    assert by_name["tool_2"].parent_span_id == by_name["Worker2"].span_id
    assert by_name["Worker1"].parent_span_id == by_name["root"].span_id
    assert by_name["Worker2"].parent_span_id == by_name["root"].span_id


@pytest.mark.asyncio
async def test_deeply_nested_concurrent():
    """Orchestrator → gather(A, B), where A internally does gather(C, D).

    Verifies the full tree is correct through multiple nesting levels.
    """
    async with collect_trace() as spans:

        @profile_agent(name="C")
        async def agent_c() -> None:
            await asyncio.sleep(0.01)

        @profile_agent(name="D")
        async def agent_d() -> None:
            await asyncio.sleep(0.01)

        @profile_agent(name="A")
        async def agent_a() -> None:
            await asyncio.gather(agent_c(), agent_d())

        @profile_agent(name="B")
        async def agent_b() -> None:
            await asyncio.sleep(0.02)

        async with span_scope("root", SpanKind.AGENT, agent_name="Root"):
            await asyncio.gather(agent_a(), agent_b())

    by_name = {s.name: s for s in spans}

    # C and D are children of A
    assert by_name["C"].parent_span_id == by_name["A"].span_id
    assert by_name["D"].parent_span_id == by_name["A"].span_id

    # A and B are children of root
    assert by_name["A"].parent_span_id == by_name["root"].span_id
    assert by_name["B"].parent_span_id == by_name["root"].span_id


@pytest.mark.asyncio
async def test_sequential_span_nesting():
    """Sequential await (no gather) correctly nests spans.

    When agent_a awaits agent_b directly (no create_task), they share the
    same task context, so agent_b sees agent_a's span as its parent.
    """
    async with collect_trace() as spans:

        @profile_agent(name="Inner")
        async def inner() -> str:
            async with span_scope("inner_llm", SpanKind.LLM, model="gpt-4o"):
                pass
            return "done"

        @profile_agent(name="Outer")
        async def outer() -> str:
            return await inner()

        await outer()

    by_name = {s.name: s for s in spans}

    # Inner is a child of Outer
    assert by_name["Inner"].parent_span_id == by_name["Outer"].span_id
    # inner_llm is a child of Inner
    assert by_name["inner_llm"].parent_span_id == by_name["Inner"].span_id


@pytest.mark.asyncio
async def test_span_fields_populated():
    """Verify that decorated spans have correct kind, agent_name, and input_hash."""
    async with collect_trace() as spans:

        @profile_agent(name="TestAgent")
        async def my_agent(query: str) -> str:
            return f"answer to {query}"

        await my_agent("hello world")

    assert len(spans) == 1
    s = spans[0]
    assert s.name == "TestAgent"
    assert s.kind == SpanKind.AGENT
    assert s.agent_name == "TestAgent"
    assert s.operation == "invoke_agent"
    assert s.input_hash is not None
    assert len(s.input_hash) == 16  # SHA-256 hex prefix
    assert s.start_ns > 0
    assert s.end_ns >= s.start_ns
    assert s.trace_id  # non-empty


@pytest.mark.asyncio
async def test_profile_tool_decorator():
    """Verify profile_tool creates TOOL spans."""
    async with collect_trace() as spans:

        @profile_tool(name="web_search")
        async def search(query: str) -> str:
            return f"results for {query}"

        await search("python asyncio")

    assert len(spans) == 1
    s = spans[0]
    assert s.name == "web_search"
    assert s.kind == SpanKind.TOOL
    assert s.operation == "execute_tool"


@pytest.mark.asyncio
async def test_same_input_hash_for_same_args():
    """Same arguments should produce the same input_hash (for duplicate detection)."""
    async with collect_trace() as spans:

        @profile_agent(name="Repeater")
        async def repeater(x: int) -> int:
            return x * 2

        await repeater(42)
        await repeater(42)
        await repeater(99)

    hashes = [s.input_hash for s in spans]
    assert hashes[0] == hashes[1]  # same input → same hash
    assert hashes[0] != hashes[2]  # different input → different hash


@pytest.mark.asyncio
async def test_collect_trace_isolation():
    """Nested collect_trace blocks don't leak spans."""
    async with collect_trace() as outer_spans:

        @profile_agent(name="Outer")
        async def outer_fn() -> None:
            pass

        await outer_fn()

        async with collect_trace() as inner_spans:

            @profile_agent(name="Inner")
            async def inner_fn() -> None:
                pass

            await inner_fn()

    # Inner collector captured Inner, not Outer
    assert len(inner_spans) == 1
    assert inner_spans[0].name == "Inner"

    # Outer collector captured Outer (before the inner block replaced the collector)
    assert any(s.name == "Outer" for s in outer_spans)


@pytest.mark.asyncio
async def test_many_concurrent_agents():
    """Stress test: 10 concurrent agents, each with a child span."""
    async with collect_trace() as spans:

        async def make_agent(i: int) -> None:
            @profile_agent(name=f"Agent{i}")
            async def agent_fn() -> None:
                await asyncio.sleep(0.005)
                async with span_scope(f"llm_{i}", SpanKind.LLM, model="test"):
                    await asyncio.sleep(0.005)

            await agent_fn()

        await asyncio.gather(*(make_agent(i) for i in range(10)))

    # Should have 20 spans: 10 agent + 10 LLM
    assert len(spans) == 20

    by_name = {s.name: s for s in spans}
    for i in range(10):
        agent_span = by_name[f"Agent{i}"]
        llm_span = by_name[f"llm_{i}"]
        # Each LLM span's parent must be its own agent, not any other
        assert llm_span.parent_span_id == agent_span.span_id, (
            f"llm_{i} parent should be Agent{i} ({agent_span.span_id}), "
            f"got {llm_span.parent_span_id}"
        )


@pytest.mark.asyncio
async def test_mark_first_token_streaming():
    """Verify mark_first_token records TTFT correctly."""
    from spandrift.profiler import mark_first_token

    async with collect_trace() as spans:
        async with span_scope("streaming_llm", SpanKind.LLM, model="gpt-4o"):
            await asyncio.sleep(0.01)
            mark_first_token()  # first token arrived
            await asyncio.sleep(0.01)

    assert len(spans) == 1
    s = spans[0]
    assert s.first_token_ns is not None
    assert s.first_token_ns > s.start_ns
    assert s.first_token_ns < s.end_ns
    assert s.ttft_ms is not None
    assert 5 <= s.ttft_ms <= 20

