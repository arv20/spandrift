"""Tests for diff.py comparison logic and threshold checking."""

from __future__ import annotations

import polars as pl
import pytest

from spandrift.analysis import AnalysisResult
from spandrift.diff import check_thresholds, compute_diff, render_diff_report


def make_mock_result(agent_costs: dict[str, tuple[float, float]]) -> AnalysisResult:
    """Helper to create AnalysisResult with given agent -> (cost, wall_clock_ms)."""
    rows = []
    for agent, (cost, wall_ms) in agent_costs.items():
        rows.append(
            {
                "agent_name": agent,
                "total_cost": cost,
                "wall_clock_ms": wall_ms,
                "compute_time_ms": wall_ms,
                "llm_calls": 1,
                "total_input_tokens": 100,
                "total_output_tokens": 100,
            }
        )
    rollup = pl.DataFrame(rows) if rows else pl.DataFrame()
    total_cost = sum(c for c, _ in agent_costs.values()) if agent_costs else 0.0
    return AnalysisResult(
        rollup=rollup,
        duplicates=pl.DataFrame(),
        retry_storms=[],
        ttft_outliers=pl.DataFrame(),
        total_spans=len(rows),
        total_cost=total_cost,
        wall_clock_ms=1000.0,
        compute_time_ms=1000.0,
    )


def test_diff_cost_and_latency_deltas():
    base = make_mock_result({"AgentA": (1.0, 1000.0)})
    head = make_mock_result({"AgentA": (1.2, 1100.0)})  # +20% cost, +10% latency

    diffs = compute_diff(base, head)
    assert len(diffs) == 1
    d = diffs[0]
    assert d.agent_name == "AgentA"
    assert pytest.approx(d.cost_delta, rel=1e-4) == 0.20
    assert pytest.approx(d.latency_delta, rel=1e-4) == 0.10


def test_check_thresholds():
    base = make_mock_result({"AgentA": (1.0, 1000.0)})
    head = make_mock_result({"AgentA": (1.15, 1050.0)})  # +15% cost, +5% latency

    diffs = compute_diff(base, head)
    # Exceeds cost threshold of 10%
    assert check_thresholds(diffs, cost_threshold=0.10, latency_threshold=0.20) is True
    # Does not exceed cost threshold of 20%
    assert check_thresholds(diffs, cost_threshold=0.20, latency_threshold=0.20) is False


def test_render_diff_report():
    base = make_mock_result({"AgentA": (1.0, 1000.0)})
    head = make_mock_result({"AgentA": (1.2, 1100.0)})
    diffs = compute_diff(base, head)
    output = render_diff_report(diffs, base, head, "base.json", "head.json")
    assert "Spandrift Diff" in output
    assert "AgentA" in output
    assert "+20.0%" in output
