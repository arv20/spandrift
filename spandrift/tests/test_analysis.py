"""Tests for analysis.py diagnostic calculations."""

from __future__ import annotations

import polars as pl
import pytest

from spandrift.analysis import (
    _interval_union_duration_ms,
    analyze,
    compute_rollup,
    detect_duplicates,
    detect_latency_outliers,
    detect_retry_storms,
    spans_to_dataframe,
)
from spandrift.models import Span, SpanKind


def test_interval_union_duration_ms():
    # Empty
    assert _interval_union_duration_ms([]) == 0.0

    # Non-overlapping intervals: [0, 2s] and [10s, 12s] -> total 4s = 4000ms
    intervals = [(0, 2_000_000_000), (10_000_000_000, 12_000_000_000)]
    assert _interval_union_duration_ms(intervals) == 4000.0

    # Overlapping intervals: [0, 5s] and [3s, 8s] -> union [0, 8s] = 8000ms
    intervals = [(0, 5_000_000_000), (3_000_000_000, 8_000_000_000)]
    assert _interval_union_duration_ms(intervals) == 8000.0

    # Contained intervals: [0, 10s] and [2s, 5s] -> union [0, 10s] = 10000ms
    intervals = [(0, 10_000_000_000), (2_000_000_000, 5_000_000_000)]
    assert _interval_union_duration_ms(intervals) == 10000.0


def test_compute_rollup_interval_union():
    # Two separate non-contiguous calls for AgentA: [0s, 1s] and [10s, 11s]
    # Naive max-min would give 11s. Interval union correctly gives 2s (2000ms).
    spans = [
        Span(
            trace_id="t1",
            span_id="s1",
            parent_span_id=None,
            name="call1",
            kind=SpanKind.AGENT,
            agent_name="AgentA",
            start_ns=0,
            end_ns=1_000_000_000,
            cost=0.01,
            input_tokens=100,
            output_tokens=50,
        ),
        Span(
            trace_id="t1",
            span_id="s2",
            parent_span_id=None,
            name="call2",
            kind=SpanKind.AGENT,
            agent_name="AgentA",
            start_ns=10_000_000_000,
            end_ns=11_000_000_000,
            cost=0.02,
            input_tokens=200,
            output_tokens=100,
        ),
    ]
    df = spans_to_dataframe(spans)
    rollup = compute_rollup(df)

    assert rollup.height == 1
    row = rollup.row(0, named=True)
    assert row["agent_name"] == "AgentA"
    assert pytest.approx(row["total_cost"]) == 0.03
    assert row["wall_clock_ms"] == 2000.0  # not 11000.0!
    assert row["compute_time_ms"] == 2000.0
    assert row["total_input_tokens"] == 300
    assert row["total_output_tokens"] == 150


def test_detect_duplicates():
    spans = [
        Span(
            trace_id="t1",
            span_id="s1",
            parent_span_id=None,
            name="agent",
            kind=SpanKind.AGENT,
            agent_name="SearchAgent",
            start_ns=0,
            end_ns=1000,
            input_hash="hash_abc",
            cost=0.05,
        ),
        Span(
            trace_id="t1",
            span_id="s2",
            parent_span_id=None,
            name="agent",
            kind=SpanKind.AGENT,
            agent_name="SearchAgent",
            start_ns=2000,
            end_ns=3000,
            input_hash="hash_abc",
            cost=0.05,
        ),
        Span(
            trace_id="t1",
            span_id="s3",
            parent_span_id=None,
            name="agent",
            kind=SpanKind.AGENT,
            agent_name="SearchAgent",
            start_ns=4000,
            end_ns=5000,
            input_hash="hash_xyz",
            cost=0.05,
        ),
    ]
    df = spans_to_dataframe(spans)
    dups = detect_duplicates(df)

    assert dups.height == 1
    row = dups.row(0, named=True)
    assert row["agent_name"] == "SearchAgent"
    assert row["input_hash"] == "hash_abc"
    assert row["call_count"] == 2
    assert pytest.approx(row["estimated_waste"]) == 0.05


def test_detect_duplicates_subtree_cost():
    # Agent spans have cost=0.0, but child LLM spans have cost=0.05
    spans = [
        # Call 1: Agent (cost 0) -> Child LLM (cost 0.05)
        Span(
            trace_id="t1",
            span_id="agent_1",
            parent_span_id=None,
            name="SearchAgent",
            kind=SpanKind.AGENT,
            agent_name="SearchAgent",
            start_ns=0,
            end_ns=1000,
            input_hash="hash_dup",
            cost=None,
        ),
        Span(
            trace_id="t1",
            span_id="llm_1",
            parent_span_id="agent_1",
            name="chat gpt-4o",
            kind=SpanKind.LLM,
            agent_name="SearchAgent",
            start_ns=100,
            end_ns=900,
            cost=0.05,
        ),
        # Call 2 (duplicate): Agent (cost 0) -> Child LLM (cost 0.05)
        Span(
            trace_id="t1",
            span_id="agent_2",
            parent_span_id=None,
            name="SearchAgent",
            kind=SpanKind.AGENT,
            agent_name="SearchAgent",
            start_ns=2000,
            end_ns=3000,
            input_hash="hash_dup",
            cost=None,
        ),
        Span(
            trace_id="t1",
            span_id="llm_2",
            parent_span_id="agent_2",
            name="chat gpt-4o",
            kind=SpanKind.LLM,
            agent_name="SearchAgent",
            start_ns=2100,
            end_ns=2900,
            cost=0.05,
        ),
    ]
    df = spans_to_dataframe(spans)
    dups = detect_duplicates(df)

    assert dups.height == 1
    row = dups.row(0, named=True)
    assert row["agent_name"] == "SearchAgent"
    assert row["input_hash"] == "hash_dup"
    assert row["call_count"] == 2
    assert pytest.approx(row["total_cost"]) == 0.10
    assert pytest.approx(row["estimated_waste"]) == 0.05


def test_detect_retry_storms():
    # 4 consecutive calls with the same name and exact input_hash
    spans = [
        Span(
            trace_id="t1",
            span_id=f"span_{i}",
            parent_span_id="root",
            name="web_search",
            kind=SpanKind.TOOL,
            start_ns=i * 1000,
            end_ns=(i + 1) * 1000,
            input_hash="query_hash_1",
        )
        for i in range(4)
    ]
    df = spans_to_dataframe(spans)
    storms = detect_retry_storms(df, threshold=3)

    assert len(storms) == 1
    assert storms[0].agent_or_tool == "web_search"
    assert storms[0].chain_length == 4
    assert storms[0].span_ids == ["span_0", "span_1", "span_2", "span_3"]
    assert storms[0].input_hash == "query_hash_1"
    assert storms[0].similarity == 1.0


def test_detect_fuzzy_retry_storms():
    # 3 consecutive calls with slightly diverging inputs ("attempt 1 query...", "attempt 2 query...")
    spans = [
        Span(
            trace_id="t1",
            span_id="s1",
            parent_span_id=None,
            name="ResearchAgent",
            kind=SpanKind.AGENT,
            start_ns=1000,
            end_ns=2000,
            input_hash="hash_1",
            input_value="query: latest python release notes version 3.12 attempt 1",
        ),
        Span(
            trace_id="t1",
            span_id="s2",
            parent_span_id=None,
            name="ResearchAgent",
            kind=SpanKind.AGENT,
            start_ns=2100,
            end_ns=3000,
            input_hash="hash_2",
            input_value="query: latest python release notes version 3.12 attempt 2",
        ),
        Span(
            trace_id="t1",
            span_id="s3",
            parent_span_id=None,
            name="ResearchAgent",
            kind=SpanKind.AGENT,
            start_ns=3100,
            end_ns=4000,
            input_hash="hash_3",
            input_value="query: latest python release notes version 3.12 attempt 3",
        ),
    ]
    df = spans_to_dataframe(spans)
    storms = detect_retry_storms(df, threshold=3, similarity_threshold=0.80)

    assert len(storms) == 1
    assert storms[0].agent_or_tool == "ResearchAgent"
    assert storms[0].chain_length == 3
    assert storms[0].similarity >= 0.80


def test_missing_input_not_flagged_as_duplicate_or_retry_storm():
    """Ensure spans with missing input_value and input_hash are never falsely flagged.

    Absent data must not be treated as a similarity signal (token_jaccard_similarity
    returns 0.0 when either input is None).
    """
    from spandrift.analysis import token_jaccard_similarity

    # Jaccard similarity unit checks on None
    assert token_jaccard_similarity(None, None) == 0.0
    assert token_jaccard_similarity("some query", None) == 0.0
    assert token_jaccard_similarity(None, "some query") == 0.0
    assert token_jaccard_similarity("", "") == 0.0

    # 4 consecutive same-named spans with NO input_hash and NO input_value
    spans = [
        Span(
            trace_id="t1",
            span_id=f"llm_{i}",
            parent_span_id=None,
            name="chat gpt-4o",
            kind=SpanKind.LLM,
            agent_name="FactChecker",
            start_ns=i * 1000,
            end_ns=(i + 1) * 1000,
            input_hash=None,
            input_value=None,
        )
        for i in range(4)
    ]
    df = spans_to_dataframe(spans)

    # Must NOT be flagged as duplicates
    dups = detect_duplicates(df)
    assert dups.is_empty()

    # Must NOT be flagged as a retry storm
    storms = detect_retry_storms(df, threshold=2)
    assert len(storms) == 0


def test_detect_latency_outliers():
    # Model group with baseline durations around 100ms, and one outlier at 1000ms
    spans = [
        Span(
            trace_id="t1",
            span_id=f"s_{i}",
            parent_span_id=None,
            name="chat",
            kind=SpanKind.LLM,
            model="gpt-4o",
            start_ns=i * 1_000_000_000,
            end_ns=i * 1_000_000_000 + 100_000_000,  # 100ms
        )
        for i in range(20)
    ]
    # Add an outlier
    spans.append(
        Span(
            trace_id="t1",
            span_id="s_outlier",
            parent_span_id=None,
            name="chat",
            kind=SpanKind.LLM,
            model="gpt-4o",
            start_ns=21 * 1_000_000_000,
            end_ns=21 * 1_000_000_000 + 1_000_000_000,  # 1000ms (10x baseline)
        )
    )

    df = spans_to_dataframe(spans)
    outliers = detect_latency_outliers(df, multiplier=2.0)

    assert outliers.height == 1
    row = outliers.row(0, named=True)
    assert row["span_id"] == "s_outlier"
    assert row["model"] == "gpt-4o"
    assert row["metric"] == "duration"
    assert row["latency_ms"] == 1000.0
    assert row["ratio"] > 2.0


def test_analyze_full_suite():
    spans = [
        Span(
            trace_id="t1",
            span_id="s1",
            parent_span_id=None,
            name="Orchestrator",
            kind=SpanKind.AGENT,
            agent_name="Orchestrator",
            start_ns=0,
            end_ns=5_000_000_000,
            cost=0.02,
        ),
        Span(
            trace_id="t1",
            span_id="s2",
            parent_span_id="s1",
            name="Worker",
            kind=SpanKind.AGENT,
            agent_name="Worker",
            start_ns=1_000_000_000,
            end_ns=3_000_000_000,
            cost=0.03,
        ),
    ]
    result = analyze(spans)

    assert result.total_spans == 2
    assert pytest.approx(result.total_cost) == 0.05
    assert result.wall_clock_ms == 5000.0
    assert result.compute_time_ms == 7000.0
    assert result.rollup.height == 2
