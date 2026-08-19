"""Tests for cost_engine.py pricing logic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spandrift.cost_engine import (
    ModelPricing,
    _load_user_overrides,
    _resolve_pricing,
    compute_cost,
    enrich_spans,
)
from spandrift.models import Span, SpanKind


def make_llm_span(
    model: str,
    provider: str = "openai",
    input_tokens: int = 1000,
    output_tokens: int = 500,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> Span:
    return Span(
        trace_id="t1",
        span_id="s1",
        parent_span_id=None,
        name=f"chat {model}",
        kind=SpanKind.LLM,
        start_ns=1_000_000_000,
        end_ns=2_000_000_000,
        model=model,
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
    )


def test_pricing_exact_match():
    span = make_llm_span("gpt-4o", provider="openai", input_tokens=1_000_000, output_tokens=1_000_000)
    # gpt-4o: input=$2.50/M, output=$10.00/M
    cost = compute_cost(span)
    assert cost is not None
    assert pytest.approx(cost, rel=1e-4) == 12.50


def test_pricing_prefix_match():
    # gpt-4o-2024-08-06 matches gpt-4o
    span = make_llm_span("gpt-4o-2024-08-06", provider="openai", input_tokens=1_000_000, output_tokens=0)
    cost = compute_cost(span)
    assert cost is not None
    assert pytest.approx(cost, rel=1e-4) == 2.50


def test_pricing_cache_read_and_write():
    # claude-3-5-sonnet-20241022: input=$3.00, output=$15.00, cache_read=$0.30, cache_write=$3.75
    # Total input: 100k, 50k cached -> 50k uncached ($0.15) + 50k cached ($0.015)
    # Output: 10k ($0.15) + Cache write: 20k ($0.075) -> Total = $0.39
    span = make_llm_span(
        "claude-3-5-sonnet-20241022",
        provider="anthropic",
        input_tokens=100_000,
        output_tokens=10_000,
        cache_read_tokens=50_000,
        cache_write_tokens=20_000,
    )
    cost = compute_cost(span)
    assert cost is not None
    assert pytest.approx(cost, rel=1e-4) == 0.39


def test_non_llm_span_cost_is_none():
    span = Span(
        trace_id="t1",
        span_id="s1",
        parent_span_id=None,
        name="web_search",
        kind=SpanKind.TOOL,
        start_ns=1000,
        end_ns=2000,
        input_tokens=500,
        output_tokens=500,
        model="gpt-4o",
    )
    assert compute_cost(span) is None


def test_unknown_model_cost_is_none():
    span = make_llm_span("non-existent-model-xyz", provider="unknown")
    assert compute_cost(span) is None


def test_enrich_spans():
    spans = [
        make_llm_span("gpt-4o", provider="openai", input_tokens=1000, output_tokens=1000),
        Span(
            trace_id="t1",
            span_id="s2",
            parent_span_id=None,
            name="tool",
            kind=SpanKind.TOOL,
            start_ns=100,
            end_ns=200,
        ),
    ]
    enriched = enrich_spans(spans)
    assert enriched[0].cost is not None
    assert enriched[0].cost > 0
    assert enriched[1].cost is None


def test_user_pricing_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    override_file = tmp_path / "custom_prices.json"
    override_file.write_text(
        json.dumps(
            {
                "custom_provider/custom_model": {
                    "input_per_mtok": 5.0,
                    "output_per_mtok": 20.0,
                }
            }
        )
    )
    monkeypatch.setenv("SPANDRIFT_PRICES_PATH", str(override_file))

    pricing = _resolve_pricing("custom_provider", "custom_model")
    assert pricing is not None
    assert pricing.input_per_mtok == 5.0
    assert pricing.output_per_mtok == 20.0
