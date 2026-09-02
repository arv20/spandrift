"""Two-run comparison: cost and latency deltas with CI-friendly exit codes."""

from __future__ import annotations

import dataclasses
import io

import polars as pl
from rich.console import Console
from rich.table import Table

from spandrift.analysis import AnalysisResult


@dataclasses.dataclass(frozen=True, slots=True)
class DiffResult:
    """Per-agent comparison between a base and head run."""

    agent_name: str
    base_cost: float
    head_cost: float
    cost_delta: float  # (head - base) / base, as a fraction
    base_wall_ms: float
    head_wall_ms: float
    latency_delta: float  # (head - base) / base, as a fraction


def compute_diff(base: AnalysisResult, head: AnalysisResult) -> list[DiffResult]:
    """Compare two analysis results and produce per-agent deltas.

    Cost and latency deltas are expressed as fractions: 0.10 = 10% regression,
    -0.05 = 5% improvement.
    """
    if base.rollup.height == 0 and head.rollup.height == 0:
        return []

    # Use an outer join so agents present in only one run still appear
    base_df = base.rollup.select(
        pl.col("agent_name"),
        pl.col("total_cost").alias("base_cost"),
        pl.col("wall_clock_ms").alias("base_wall_ms"),
    )
    head_df = head.rollup.select(
        pl.col("agent_name"),
        pl.col("total_cost").alias("head_cost"),
        pl.col("wall_clock_ms").alias("head_wall_ms"),
    )

    joined = base_df.join(head_df, on="agent_name", how="full", coalesce=True)

    results: list[DiffResult] = []
    for row in joined.iter_rows(named=True):
        agent = row["agent_name"] or "unknown"
        bc = row.get("base_cost") or 0.0
        hc = row.get("head_cost") or 0.0
        bw = row.get("base_wall_ms") or 0.0
        hw = row.get("head_wall_ms") or 0.0

        cost_delta = (hc - bc) / bc if bc > 0 else (1.0 if hc > 0 else 0.0)
        lat_delta = (hw - bw) / bw if bw > 0 else (1.0 if hw > 0 else 0.0)

        results.append(
            DiffResult(
                agent_name=agent,
                base_cost=bc,
                head_cost=hc,
                cost_delta=cost_delta,
                base_wall_ms=bw,
                head_wall_ms=hw,
                latency_delta=lat_delta,
            )
        )

    return results


def _fmt_cost(c: float) -> str:
    if c < 0.01:
        return f"${c:.6f}"
    return f"${c:.4f}"


def _fmt_pct(delta: float) -> str:
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta * 100:.1f}%"


def _fmt_ms(ms: float) -> str:
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{ms / 1000:.1f}s"


def render_diff_report(
    diffs: list[DiffResult],
    base_result: AnalysisResult,
    head_result: AnalysisResult,
    base_source: str = "base",
    head_source: str = "head",
) -> str:
    """Render a diff report to the terminal."""
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=True, width=80)

    # Summary
    bc = base_result.total_cost or 0
    hc = head_result.total_cost or 0
    total_cost_delta = (hc - bc) / bc if bc > 0 else 0
    console.print(
        f"[bold]Spandrift Diff: {base_source} → {head_source}[/bold]\n"
        f"Total cost: {_fmt_cost(bc)} → {_fmt_cost(hc)} ({_fmt_pct(total_cost_delta)})"
    )

    table = Table(title="Per-Agent Deltas", show_lines=False)
    table.add_column("Agent", style="cyan")
    table.add_column("Base Cost", justify="right")
    table.add_column("Head Cost", justify="right")
    table.add_column("Cost Δ", justify="right")
    table.add_column("Base Latency", justify="right")
    table.add_column("Head Latency", justify="right")
    table.add_column("Latency Δ", justify="right")

    for d in diffs:
        cost_style = "red" if d.cost_delta > 0.05 else ("green" if d.cost_delta < -0.05 else "")
        lat_style = (
            "red" if d.latency_delta > 0.05 else ("green" if d.latency_delta < -0.05 else "")
        )
        table.add_row(
            d.agent_name,
            _fmt_cost(d.base_cost),
            _fmt_cost(d.head_cost),
            f"[{cost_style}]{_fmt_pct(d.cost_delta)}[/{cost_style}]" if cost_style else _fmt_pct(d.cost_delta),
            _fmt_ms(d.base_wall_ms),
            _fmt_ms(d.head_wall_ms),
            f"[{lat_style}]{_fmt_pct(d.latency_delta)}[/{lat_style}]" if lat_style else _fmt_pct(d.latency_delta),
        )

    console.print(table)
    return buffer.getvalue()


def check_thresholds(
    diffs: list[DiffResult],
    cost_threshold: float = 0.10,
    latency_threshold: float = 0.20,
) -> bool:
    """Return True if any agent exceeds the regression thresholds.

    Used for CI gating: non-zero exit when this returns True.
    """
    for d in diffs:
        if d.cost_delta > cost_threshold:
            return True
        if d.latency_delta > latency_threshold:
            return True
    return False
