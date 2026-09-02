"""Multi-agent workflow demo using smolagents + spandrift.profiler.

Demonstrates:
1. Multi-agent orchestration with 4 agents: Orchestrator, ResearchAgent, FactChecker, WriterAgent
2. Concurrent fan-out via asyncio.gather (ResearchAgent and FactChecker run concurrently)
3. Correct parent/child span attribution across concurrent tasks via @profile_agent
4. OpenTelemetry instrumentation integration via SmolagentsInstrumentor
5. Planted duplicate call (ResearchAgent invoked twice with identical query)
6. Planted retry storm (FactChecker retrying web_search 4 times with identical input)
7. Generates demo/base_trace.json (clean) and demo/head_trace.json (regressed)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import time
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from openinference.instrumentation.smolagents import SmolagentsInstrumentor
from smolagents import ChatMessage, MessageRole, Model, TokenUsage, Tool

from spandrift.ingest import save_otlp_json, spans_from_otel_sdk
from spandrift.models import Span, SpanKind
from spandrift.profiler import (
    collect_trace,
    mark_first_token,
    profile_agent,
    profile_tool,
    span_scope,
)


# ---------------------------------------------------------------------------
# Deterministic Mock Model for local, zero-API-key execution
# ---------------------------------------------------------------------------

class DemoLLM(Model):
    """Deterministic LLM model for the demo that emits realistic tokens and timing."""

    def __init__(self, model_id: str = "gpt-4o", provider: str = "openai", is_slow: bool = False):
        super().__init__()
        self.model_id = model_id
        self.provider = provider
        self.is_slow = is_slow
        self.call_count = 0

    def generate(self, messages: list[Any], stop_sequences: list[str] | None = None, **kwargs: Any) -> ChatMessage:
        self.call_count += 1
        # Simulate LLM inference duration
        if self.is_slow:
            time.sleep(0.08)
        else:
            time.sleep(0.02)

        return ChatMessage(
            role=MessageRole.ASSISTANT,
            content="Key findings: Quantum Key Distribution (QKD) and lattice-based cryptography provide quantum resistance.",
            token_usage=TokenUsage(input_tokens=420, output_tokens=180),
        )


# ---------------------------------------------------------------------------
# Custom smolagents Tool definitions
# ---------------------------------------------------------------------------

class WebSearchTool(Tool):
    name = "web_search"
    description = "Searches the web for academic papers, standards, and technical facts."
    inputs = {"query": {"type": "string", "description": "The search query"}}
    output_type = "string"

    def forward(self, query: str) -> str:
        time.sleep(0.01)
        return f"Retrieved technical document for: {query}"


# ---------------------------------------------------------------------------
# Instrumented Agent Orchestration Layer
# ---------------------------------------------------------------------------

@profile_tool(name="web_search")
async def execute_web_search(query: str) -> str:
    """Tool wrapper instrumented with @profile_tool."""
    await asyncio.sleep(0.01)
    return f"Search result: NIST FIPS 203/204 standard for {query}"


@profile_agent(name="ResearchAgent")
async def run_research_agent(topic: str) -> str:
    """Sub-agent 1: conducts research by querying tools and models."""
    await asyncio.sleep(0.02)
    # Simulate LLM call within agent
    async with span_scope(
        name="chat gpt-4o",
        kind=SpanKind.LLM,
        model="gpt-4o",
        provider="openai",
        operation="chat",
        input_tokens=520,
        output_tokens=210,
    ):
        await asyncio.sleep(0.02)
        mark_first_token()  # record streaming first-token
        await asyncio.sleep(0.02)

    await execute_web_search(f"state of the art in {topic}")
    return f"Research compiled for topic: {topic}"


@profile_agent(name="FactChecker")
async def run_fact_checker(claim: str, *, simulate_retry_storm: bool = False) -> str:
    """Sub-agent 2: verifies claims.

    When simulate_retry_storm=True, executes 4 repeated queries with
    identical input to simulate an agent trapped in a tool retry loop.
    """
    await asyncio.sleep(0.01)
    async with span_scope(
        name="chat gpt-4o",
        kind=SpanKind.LLM,
        model="gpt-4o",
        provider="openai",
        operation="chat",
        input_tokens=350,
        output_tokens=120,
    ):
        await asyncio.sleep(0.02)
        mark_first_token()
        await asyncio.sleep(0.01)

    if simulate_retry_storm:
        # Deliberate retry storm: 4 consecutive calls with identical input
        query = f"verify claim {claim}"
        for _ in range(4):
            await execute_web_search(query)
    else:
        await execute_web_search(f"verify claim {claim}")

    return f"Verification verified for claim: {claim}"


@profile_agent(name="WriterAgent")
async def run_writer_agent(research_data: str, fact_data: str) -> str:
    """Sub-agent 3: compiles final synthesized report."""
    await asyncio.sleep(0.02)
    async with span_scope(
        name="chat gpt-4o",
        kind=SpanKind.LLM,
        model="gpt-4o",
        provider="openai",
        operation="chat",
        input_tokens=850,
        output_tokens=420,
    ):
        await asyncio.sleep(0.03)
        mark_first_token()
        await asyncio.sleep(0.02)

    return f"Executive Briefing based on {research_data} and {fact_data}"


@profile_agent(name="Orchestrator")
async def run_orchestration_workflow(
    topic: str,
    *,
    has_redundancy: bool = False,
) -> str:
    """Top-level multi-agent workflow.

    Demonstrates concurrent fan-out via asyncio.gather(ResearchAgent, FactChecker).
    """
    # 1. Concurrent fan-out: launch ResearchAgent and FactChecker concurrently
    research_coro = run_research_agent(topic)
    fact_coro = run_fact_checker(topic, simulate_retry_storm=has_redundancy)

    research_res, fact_res = await asyncio.gather(research_coro, fact_coro)

    # 2. Deliberate inefficiency: duplicate call to ResearchAgent with identical topic
    if has_redundancy:
        _ = await run_research_agent(topic)

    # 3. Final synthesis
    final_report = await run_writer_agent(research_res, fact_res)
    return final_report


# ---------------------------------------------------------------------------
# Trace Generation Runners
# ---------------------------------------------------------------------------

async def generate_trace(has_redundancy: bool) -> list[Span]:
    """Execute the workflow inside collect_trace and return collected Spans."""
    # Setup OpenTelemetry in-memory exporter for smolagents
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    try:
        SmolagentsInstrumentor().instrument(tracer_provider=provider)
    except Exception:
        pass  # Already instrumented or in-process

    topic = "quantum key distribution protocol security proof"

    async with collect_trace() as spans:
        await run_orchestration_workflow(topic, has_redundancy=has_redundancy)

    # Also collect spans emitted by smolagents
    smol_spans = spans_from_otel_sdk(exporter.get_finished_spans())
    all_spans = list(spans) + smol_spans
    return all_spans


def main() -> None:
    demo_dir = Path(__file__).parent
    demo_dir.mkdir(parents=True, exist_ok=True)

    base_path = demo_dir / "base_trace.json"
    head_path = demo_dir / "head_trace.json"

    print("================================================================")
    print("Spandrift Multi-Agent Demo")
    print("================================================================")
    print("\n1. Running baseline trace (clean execution)...")
    base_spans = asyncio.run(generate_trace(has_redundancy=False))
    save_otlp_json(base_spans, base_path)
    print(f"   Saved {len(base_spans)} spans to {base_path}")

    print("\n2. Running PR/head trace (concurrent fan-out + duplicate call + retry storm)...")
    head_spans = asyncio.run(generate_trace(has_redundancy=True))
    save_otlp_json(head_spans, head_path)
    print(f"   Saved {len(head_spans)} spans to {head_path}")

    print("\nTraces successfully generated.")


if __name__ == "__main__":
    main()
