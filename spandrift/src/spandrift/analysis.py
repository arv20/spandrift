# Polars is used here because span analysis is fundamentally columnar batch
# aggregation: we're computing grouped statistics (per-agent cost, per-model
# latency percentiles, duplicate detection by input hash) over a DataFrame of
# spans. Polars' lazy evaluation and vectorized operations make these
# aggregations natural to express and efficient on datasets of thousands of
# spans — which is realistic for a multi-agent run with retries.

from __future__ import annotations

import dataclasses
from itertools import groupby
from typing import Any

import polars as pl

from spandrift.models import Span


def _interval_union_duration_ms(intervals: list[tuple[int, int]]) -> float:
    """Compute the total wall-clock duration of a set of intervals in milliseconds.

    Uses an interval-union algorithm to avoid double-counting overlapping
    concurrent branches and avoid overstating duration across non-contiguous
    invocations (e.g. an agent invoked at t=0s..2s and again at t=10s..12s
    has a total wall-clock time of 4s, not 12s).
    """
    if not intervals:
        return 0.0

    # Filter invalid intervals and sort by start time
    valid = [(s, e) for s, e in intervals if e >= s]
    if not valid:
        return 0.0

    valid.sort(key=lambda x: x[0])

    merged: list[list[int]] = []
    for start, end in valid:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)

    total_ns = sum(end - start for start, end in merged)
    return total_ns / 1_000_000


def _propagate_agent_names(spans: list[Span]) -> dict[str, str]:
    """Map each span_id to its resolved agent_name by walking up parent relationships."""
    by_id = {s.span_id: s for s in spans}
    resolved: dict[str, str] = {}

    def get_agent(span: Span) -> str | None:
        if span.agent_name:
            return span.agent_name
        if span.parent_span_id and span.parent_span_id in by_id:
            return get_agent(by_id[span.parent_span_id])
        return None

    for s in spans:
        name = get_agent(s)
        if name:
            resolved[s.span_id] = name
    return resolved


def _compute_subtree_costs(spans: list[Span]) -> dict[str, float]:
    """Recursively sum token costs across the entire subtree under each span."""
    children_map: dict[str, list[str]] = {}
    cost_map: dict[str, float] = {}

    for s in spans:
        cost_map[s.span_id] = s.cost or 0.0
        if s.parent_span_id:
            children_map.setdefault(s.parent_span_id, []).append(s.span_id)

    subtree_costs: dict[str, float] = {}

    def get_cost(span_id: str) -> float:
        if span_id in subtree_costs:
            return subtree_costs[span_id]
        total = cost_map.get(span_id, 0.0)
        for child_id in children_map.get(span_id, []):
            total += get_cost(child_id)
        subtree_costs[span_id] = total
        return total

    for s in spans:
        get_cost(s.span_id)

    return subtree_costs


def spans_to_dataframe(spans: list[Span]) -> pl.DataFrame:
    """Convert a list of normalized Spans into a Polars DataFrame.

    Propagates ``agent_name`` down the span tree and calculates
    ``subtree_cost`` for each span including all descendants.

    Args:
        spans: Normalized span objects from any ingestion source.

    Returns:
        A DataFrame with one row per span, including computed
        ``duration_ms``, ``ttft_ms``, and ``subtree_cost`` columns.
    """
    agent_map = _propagate_agent_names(spans)
    subtree_cost_map = _compute_subtree_costs(spans)

    rows: list[dict[str, Any]] = [
        {
            "trace_id": s.trace_id,
            "span_id": s.span_id,
            "parent_span_id": s.parent_span_id,
            "name": s.name,
            "kind": s.kind.value,
            "start_ns": s.start_ns,
            "end_ns": s.end_ns,
            "agent_name": agent_map.get(s.span_id, s.agent_name),
            "model": s.model,
            "provider": s.provider,
            "operation": s.operation,
            "input_tokens": s.input_tokens,
            "output_tokens": s.output_tokens,
            "cache_read_tokens": s.cache_read_tokens,
            "cache_write_tokens": s.cache_write_tokens,
            "cost": s.cost,
            "subtree_cost": subtree_cost_map.get(s.span_id, s.cost or 0.0),
            "input_hash": s.input_hash,
            "input_value": s.input_value,
            "first_token_ns": s.first_token_ns,
            "ttft_ms": s.ttft_ms,
            "duration_ms": s.duration_ms,
        }
        for s in spans
    ]
    if not rows:
        return pl.DataFrame(
            schema={
                "trace_id": pl.Utf8,
                "span_id": pl.Utf8,
                "parent_span_id": pl.Utf8,
                "name": pl.Utf8,
                "kind": pl.Utf8,
                "start_ns": pl.Int64,
                "end_ns": pl.Int64,
                "agent_name": pl.Utf8,
                "model": pl.Utf8,
                "provider": pl.Utf8,
                "operation": pl.Utf8,
                "input_tokens": pl.Int64,
                "output_tokens": pl.Int64,
                "cache_read_tokens": pl.Int64,
                "cache_write_tokens": pl.Int64,
                "cost": pl.Float64,
                "subtree_cost": pl.Float64,
                "input_hash": pl.Utf8,
                "input_value": pl.Utf8,
                "first_token_ns": pl.Int64,
                "ttft_ms": pl.Float64,
                "duration_ms": pl.Float64,
            }
        )
    return pl.DataFrame(rows)


def compute_rollup(df: pl.DataFrame) -> pl.DataFrame:
    """Compute per-agent cost, timing, and token rollups.

    ``wall_clock_ms`` is calculated via interval union of all spans belonging
    to each agent, correctly measuring elapsed time across concurrent
    branches without overstating duration across non-contiguous calls.

    Args:
        df: Span DataFrame produced by :func:`spans_to_dataframe`.

    Returns:
        One row per agent with aggregated metrics.
    """
    if df.is_empty():
        return pl.DataFrame(
            schema={
                "agent_name": pl.Utf8,
                "total_cost": pl.Float64,
                "wall_clock_ms": pl.Float64,
                "compute_time_ms": pl.Float64,
                "llm_calls": pl.UInt32,
                "total_input_tokens": pl.Int64,
                "total_output_tokens": pl.Int64,
            }
        )

    # Compute Polars aggregations
    agg_df = (
        df.lazy()
        .filter(pl.col("agent_name").is_not_null())
        .group_by("agent_name")
        .agg(
            pl.col("cost").sum().alias("total_cost"),
            pl.col("duration_ms").sum().alias("compute_time_ms"),
            (pl.col("kind") == "llm").sum().alias("llm_calls"),
            pl.col("input_tokens").sum().alias("total_input_tokens"),
            pl.col("output_tokens").sum().alias("total_output_tokens"),
        )
        .sort("agent_name")
        .collect()
    )

    if agg_df.is_empty():
        return agg_df

    # Compute wall-clock time per agent using interval union
    agent_spans = df.filter(pl.col("agent_name").is_not_null())
    agent_wall_clocks: dict[str, float] = {}
    for agent_name, group in agent_spans.group_by("agent_name"):
        agent_str = str(agent_name[0] if isinstance(agent_name, tuple) else agent_name)
        intervals = list(
            zip(group["start_ns"].to_list(), group["end_ns"].to_list())
        )
        agent_wall_clocks[agent_str] = _interval_union_duration_ms(intervals)

    # Add wall_clock_ms column
    wall_clock_series = [
        agent_wall_clocks.get(str(row["agent_name"]), 0.0)
        for row in agg_df.iter_rows(named=True)
    ]

    return agg_df.with_columns(
        pl.Series("wall_clock_ms", wall_clock_series, dtype=pl.Float64)
    ).select(
        "agent_name",
        "total_cost",
        "wall_clock_ms",
        "compute_time_ms",
        "llm_calls",
        "total_input_tokens",
        "total_output_tokens",
    )


def detect_duplicates(df: pl.DataFrame) -> pl.DataFrame:
    """Find duplicate LLM/tool/agent calls sharing the exact same input hash per agent.

    Uses ``subtree_cost`` to ensure that duplicate agent/workflow invocations
    capture the full recursive cost of all underlying child LLM spans.
    ``estimated_waste`` is calculated as:
    total_cost × (call_count − 1) / call_count.

    Args:
        df: Span DataFrame produced by :func:`spans_to_dataframe`.

    Returns:
        One row per (agent_name, input_hash) pair that appeared more
        than once.
    """
    if df.is_empty():
        return pl.DataFrame(
            schema={
                "agent_name": pl.Utf8,
                "input_hash": pl.Utf8,
                "call_count": pl.UInt32,
                "total_cost": pl.Float64,
                "estimated_waste": pl.Float64,
            }
        )

    return (
        df.lazy()
        .filter(pl.col("input_hash").is_not_null())
        .group_by("agent_name", "input_hash")
        .agg(
            pl.len().alias("call_count"),
            pl.col("subtree_cost").sum().alias("total_cost"),
        )
        .filter(pl.col("call_count") > 1)
        .with_columns(
            (
                pl.col("total_cost")
                * (pl.col("call_count") - 1)
                / pl.col("call_count")
            ).alias("estimated_waste"),
        )
        .sort("agent_name", "input_hash")
        .collect()
    )


def token_jaccard_similarity(s1: str | None, s2: str | None) -> float:
    """Compute token-level Jaccard overlap similarity between two strings.

    Returns 0.0 when either input is missing — absent data is never a
    similarity signal.
    """
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0
    toks1 = set(s1.lower().split())
    toks2 = set(s2.lower().split())
    if not toks1 or not toks2:
        return 0.0
    return len(toks1 & toks2) / len(toks1 | toks2)


@dataclasses.dataclass(frozen=True, slots=True)
class RetryStorm:
    """A detected sequence of retried calls for the same operation with near-identical input."""

    agent_or_tool: str
    chain_length: int
    span_ids: list[str]
    input_hash: str | None
    similarity: float = 1.0


def detect_retry_storms(
    df: pl.DataFrame,
    threshold: int = 3,
    similarity_threshold: float = 0.85,
) -> list[RetryStorm]:
    """Detect retry storms — repeated calls with the same name and identical or near-duplicate input.

    Uses exact input hash matching alongside token Jaccard similarity (default: >= 0.85)
    to catch both identical retries and slightly diverging retry loops
    (e.g., "Attempt 1: query" vs "Attempt 2: query").

    Args:
        df: Span DataFrame produced by :func:`spans_to_dataframe`.
        threshold: Minimum consecutive-duplicate count to flag.
        similarity_threshold: Minimum Jaccard token overlap to consider near-duplicate.

    Returns:
        A list of :class:`RetryStorm` entries, one per detected storm.
    """
    if df.is_empty():
        return []

    sorted_df = df.sort("start_ns")
    storms: list[RetryStorm] = []

    grouped = sorted_df.select(
        "trace_id", "name", "span_id", "input_hash", "input_value", "agent_name"
    ).to_dicts()

    by_key: dict[tuple[str, str, str | None], list[dict[str, Any]]] = {}
    for row in grouped:
        key = (
            str(row["trace_id"]),
            str(row["name"]),
            str(row["agent_name"]) if row.get("agent_name") is not None else None,
        )
        by_key.setdefault(key, []).append(row)

    for (_trace_id, name, _agent_name), rows in by_key.items():
        if len(rows) < threshold:
            continue

        current_chain: list[dict[str, Any]] = [rows[0]]
        for curr in rows[1:]:
            prev = current_chain[-1]
            exact_hash = (
                curr["input_hash"] is not None
                and curr["input_hash"] == prev["input_hash"]
            )
            sim = token_jaccard_similarity(curr.get("input_value"), prev.get("input_value"))

            if exact_hash or sim >= similarity_threshold:
                current_chain.append(curr)
            else:
                if len(current_chain) >= threshold:
                    storms.append(
                        RetryStorm(
                            agent_or_tool=name,
                            chain_length=len(current_chain),
                            span_ids=[str(r["span_id"]) for r in current_chain],
                            input_hash=str(current_chain[0]["input_hash"])
                            if current_chain[0]["input_hash"] is not None
                            else None,
                            similarity=sim if not exact_hash else 1.0,
                        )
                    )
                current_chain = [curr]

        if len(current_chain) >= threshold:
            storms.append(
                RetryStorm(
                    agent_or_tool=name,
                    chain_length=len(current_chain),
                    span_ids=[str(r["span_id"]) for r in current_chain],
                    input_hash=str(current_chain[0]["input_hash"])
                    if current_chain[0]["input_hash"] is not None
                    else None,
                    similarity=1.0,
                )
            )

    return storms


def detect_latency_outliers(
    df: pl.DataFrame,
    multiplier: float = 2.0,
) -> pl.DataFrame:
    """Identify LLM spans whose latency or TTFT exceeds *multiplier* × p95 for their model.

    If a model's spans contain ``ttft_ms`` (time-to-first-token), outlier
    detection uses TTFT. Otherwise, it uses total ``duration_ms``.

    Args:
        df: Span DataFrame produced by :func:`spans_to_dataframe`.
        multiplier: How many times the p95 a span must exceed to be flagged.

    Returns:
        DataFrame with columns: ``span_id``, ``name``, ``model``, ``metric``
        ("ttft" or "duration"), ``latency_ms``, ``p95_ms``, ``ratio``.
    """
    if df.is_empty():
        return pl.DataFrame(
            schema={
                "span_id": pl.Utf8,
                "name": pl.Utf8,
                "model": pl.Utf8,
                "metric": pl.Utf8,
                "latency_ms": pl.Float64,
                "p95_ms": pl.Float64,
                "ratio": pl.Float64,
            }
        )

    llm = df.filter(pl.col("kind") == "llm")
    if llm.is_empty():
        return pl.DataFrame(
            schema={
                "span_id": pl.Utf8,
                "name": pl.Utf8,
                "model": pl.Utf8,
                "metric": pl.Utf8,
                "latency_ms": pl.Float64,
                "p95_ms": pl.Float64,
                "ratio": pl.Float64,
            }
        )

    # For models with ttft_ms available on spans, use ttft_ms; otherwise duration_ms
    outlier_rows: list[dict[str, Any]] = []

    for model_name, model_group in llm.group_by("model"):
        model_str = str(model_name[0] if isinstance(model_name, tuple) else model_name)
        has_ttft = model_group["ttft_ms"].is_not_null().any()
        metric_col = "ttft_ms" if has_ttft else "duration_ms"
        metric_label = "ttft" if has_ttft else "duration"

        valid_latencies = model_group.filter(pl.col(metric_col).is_not_null())
        if valid_latencies.is_empty():
            continue

        p95 = valid_latencies[metric_col].quantile(0.95)
        if p95 is None or p95 <= 0:
            continue

        p95_val = float(p95)
        for row in valid_latencies.iter_rows(named=True):
            lat = float(row[metric_col])
            if lat > multiplier * p95_val:
                outlier_rows.append(
                    {
                        "span_id": row["span_id"],
                        "name": row["name"],
                        "model": model_str,
                        "metric": metric_label,
                        "latency_ms": lat,
                        "p95_ms": p95_val,
                        "ratio": lat / p95_val,
                    }
                )

    if not outlier_rows:
        return pl.DataFrame(
            schema={
                "span_id": pl.Utf8,
                "name": pl.Utf8,
                "model": pl.Utf8,
                "metric": pl.Utf8,
                "latency_ms": pl.Float64,
                "p95_ms": pl.Float64,
                "ratio": pl.Float64,
            }
        )

    return (
        pl.DataFrame(outlier_rows)
        .sort("ratio", descending=True)
    )


# Alias for backward compatibility
detect_ttft_outliers = detect_latency_outliers


@dataclasses.dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Aggregated output of all diagnostic analyses on a span set."""

    rollup: pl.DataFrame
    duplicates: pl.DataFrame
    retry_storms: list[RetryStorm]
    ttft_outliers: pl.DataFrame
    total_spans: int
    total_cost: float | None
    wall_clock_ms: float
    compute_time_ms: float


def analyze(spans: list[Span], *, retry_threshold: int = 3) -> AnalysisResult:
    """Run the full analysis suite over a batch of normalized spans.

    Args:
        spans: Normalized span objects from any ingestion source.
        retry_threshold: Minimum consecutive-duplicate count to flag as retry storm.

    Returns:
        An :class:`AnalysisResult` bundling rollup, duplicate,
        retry-storm, and latency-outlier diagnostics together with
        top-level summary statistics.
    """
    df = spans_to_dataframe(spans)

    rollup = compute_rollup(df)
    duplicates = detect_duplicates(df)
    retry_storms = detect_retry_storms(df, threshold=retry_threshold)
    ttft_outliers = detect_latency_outliers(df)

    cost_sum = df["cost"].sum() if not df.is_empty() else None
    total_cost: float | None = float(cost_sum) if cost_sum is not None else None

    if df.is_empty():
        wall_clock_ms = 0.0
        compute_time_ms = 0.0
    else:
        intervals = list(zip(df["start_ns"].to_list(), df["end_ns"].to_list()))
        wall_clock_ms = _interval_union_duration_ms(intervals)
        compute_time_ms = float(df["duration_ms"].sum())

    return AnalysisResult(
        rollup=rollup,
        duplicates=duplicates,
        retry_storms=retry_storms,
        ttft_outliers=ttft_outliers,
        total_spans=len(df),
        total_cost=total_cost,
        wall_clock_ms=wall_clock_ms,
        compute_time_ms=compute_time_ms,
    )
