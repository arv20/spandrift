"""Tests for ingest.py span normalization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spandrift.ingest import (
    _flatten_attributes,
    _flatten_value,
    _hash_input,
    load_otlp_json,
    load_spans,
)
from spandrift.models import SpanKind


def test_flatten_otlp_values():
    assert _flatten_value({"stringValue": "hello"}) == "hello"
    assert _flatten_value({"intValue": "150"}) == 150
    assert _flatten_value({"doubleValue": 0.75}) == 0.75
    assert _flatten_value({"boolValue": True}) is True
    assert _flatten_value({"arrayValue": {"values": [{"stringValue": "a"}, {"stringValue": "b"}]}}) == ["a", "b"]


def test_ingest_otlp_genai_json(tmp_path: Path):
    otlp_payload = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [{"key": "service.name", "value": {"stringValue": "agent-service"}}]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "opentelemetry.instrumentation.genai"},
                        "spans": [
                            {
                                "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
                                "spanId": "00f067aa0ba902b7",
                                "parentSpanId": "",
                                "name": "invoke_agent research_assistant",
                                "kind": 1,
                                "startTimeUnixNano": "1718800000000000000",
                                "endTimeUnixNano": "1718800002500000000",
                                "attributes": [
                                    {"key": "gen_ai.operation.name", "value": {"stringValue": "invoke_agent"}},
                                    {"key": "gen_ai.agent.name", "value": {"stringValue": "research_assistant"}},
                                    {"key": "gen_ai.input.messages", "value": {"stringValue": "search topic"}},
                                ],
                                "status": {"code": 1},
                            },
                            {
                                "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
                                "spanId": "5fb397be34d23b0f",
                                "parentSpanId": "00f067aa0ba902b7",
                                "name": "chat gpt-4o",
                                "kind": 3,
                                "startTimeUnixNano": "1718800000500000000",
                                "endTimeUnixNano": "1718800001800000000",
                                "attributes": [
                                    {"key": "gen_ai.provider.name", "value": {"stringValue": "openai"}},
                                    {"key": "gen_ai.operation.name", "value": {"stringValue": "chat"}},
                                    {"key": "gen_ai.request.model", "value": {"stringValue": "gpt-4o"}},
                                    {"key": "gen_ai.response.model", "value": {"stringValue": "gpt-4o-2024-08-06"}},
                                    {"key": "gen_ai.usage.input_tokens", "value": {"intValue": "850"}},
                                    {"key": "gen_ai.usage.output_tokens", "value": {"intValue": "320"}},
                                    {"key": "gen_ai.usage.cache_read.input_tokens", "value": {"intValue": "512"}},
                                    {"key": "gen_ai.response.time_to_first_chunk", "value": {"doubleValue": 0.42}},
                                ],
                                "status": {"code": 1},
                            },
                        ],
                    }
                ],
            }
        ]
    }

    file_path = tmp_path / "otlp_genai.json"
    file_path.write_text(json.dumps(otlp_payload))

    spans = load_spans(file_path)
    assert len(spans) == 2

    # Root span
    root = spans[0]
    assert root.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert root.span_id == "00f067aa0ba902b7"
    assert root.parent_span_id is None
    assert root.kind == SpanKind.AGENT
    assert root.agent_name == "research_assistant"
    assert root.input_hash is not None

    # Child LLM span
    llm = spans[1]
    assert llm.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert llm.span_id == "5fb397be34d23b0f"
    assert llm.parent_span_id == "00f067aa0ba902b7"
    assert llm.kind == SpanKind.LLM
    assert llm.model == "gpt-4o-2024-08-06"
    assert llm.provider == "openai"
    assert llm.input_tokens == 850
    assert llm.output_tokens == 320
    assert llm.cache_read_tokens == 512
    assert llm.first_token_ns is not None
    assert llm.ttft_ms is not None
    assert pytest.approx(llm.ttft_ms, rel=1e-3) == 420.0


def test_ingest_openinference_json(tmp_path: Path):
    oi_payload = {
        "resourceSpans": [
            {
                "resource": {"attributes": []},
                "scopeSpans": [
                    {
                        "scope": {"name": "openinference.instrumentation.smolagents"},
                        "spans": [
                            {
                                "traceId": "11111111111111111111111111111111",
                                "spanId": "2222222222222222",
                                "parentSpanId": "",
                                "name": "CodeAgent.run",
                                "kind": 1,
                                "startTimeUnixNano": "1700000000000000000",
                                "endTimeUnixNano": "1700000005000000000",
                                "attributes": [
                                    {"key": "openinference.span.kind", "value": {"stringValue": "AGENT"}},
                                    {"key": "input.value", "value": {"stringValue": "solve this math problem"}},
                                ],
                            },
                            {
                                "traceId": "11111111111111111111111111111111",
                                "spanId": "3333333333333333",
                                "parentSpanId": "2222222222222222",
                                "name": "Model.__call__",
                                "kind": 3,
                                "startTimeUnixNano": "1700000001000000000",
                                "endTimeUnixNano": "1700000003000000000",
                                "attributes": [
                                    {"key": "openinference.span.kind", "value": {"stringValue": "LLM"}},
                                    {"key": "llm.model_name", "value": {"stringValue": "gpt-4o"}},
                                    {"key": "llm.token_count.prompt", "value": {"intValue": "120"}},
                                    {"key": "llm.token_count.completion", "value": {"intValue": "45"}},
                                    {"key": "input.value", "value": {"stringValue": "prompt text"}},
                                ],
                            },
                            {
                                "traceId": "11111111111111111111111111111111",
                                "spanId": "4444444444444444",
                                "parentSpanId": "2222222222222222",
                                "name": "Tool.__call__",
                                "kind": 1,
                                "startTimeUnixNano": "1700000003500000000",
                                "endTimeUnixNano": "1700000004500000000",
                                "attributes": [
                                    {"key": "openinference.span.kind", "value": {"stringValue": "TOOL"}},
                                    {"key": "tool.name", "value": {"stringValue": "python_interpreter"}},
                                    {"key": "input.value", "value": {"stringValue": "2 + 2"}},
                                ],
                            },
                        ],
                    }
                ],
            }
        ]
    }

    file_path = tmp_path / "openinference.json"
    file_path.write_text(json.dumps(oi_payload))

    spans = load_otlp_json(file_path)
    assert len(spans) == 3

    agent_span = spans[0]
    assert agent_span.kind == SpanKind.AGENT
    assert agent_span.input_hash == _hash_input("solve this math problem")

    llm_span = spans[1]
    assert llm_span.kind == SpanKind.LLM
    assert llm_span.model == "gpt-4o"
    assert llm_span.input_tokens == 120
    assert llm_span.output_tokens == 45

    tool_span = spans[2]
    assert tool_span.kind == SpanKind.TOOL
    assert tool_span.name == "python_interpreter"
