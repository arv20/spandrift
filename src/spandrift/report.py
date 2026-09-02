"""Terminal and HTML report rendering for analysis results with Visual Waterfall."""

from __future__ import annotations

import html
import io
from pathlib import Path
from typing import Any

import polars as pl
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from spandrift.analysis import AnalysisResult, RetryStorm
from spandrift.models import Span, SpanKind


def _fmt_cost(cost: float | None) -> str:
    """Format a cost value as a dollar string."""
    if cost is None:
        return "—"
    if cost < 0.01:
        return f"${cost:.6f}"
    return f"${cost:.4f}"


def _fmt_duration(ms: float) -> str:
    """Format milliseconds as a human-readable duration."""
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{ms / 1000:.1f}s"


def _fmt_tokens(n: int) -> str:
    """Format token count with comma separators."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def render_waterfall_table(spans: list[Span], bar_width: int = 28) -> Table:
    """Build a rich Table rendering an ASCII/ANSI Gantt waterfall chart.

    Shows parallel agent fan-outs, task overlapping, and TTFT waiting periods
    vs. active token stream duration.
    """
    table = Table(
        title="Execution Waterfall & Concurrency",
        show_lines=False,
        box=None,
        padding=(0, 1),
    )
    table.add_column("Span / Task", style="cyan", no_wrap=True)
    table.add_column("Timeline (░=TTFT, █=Exec)", justify="left")
    table.add_column("Duration", justify="right")
    table.add_column("TTFT", justify="right")
    table.add_column("Cost", justify="right")

    if not spans:
        return table

    t_min = min(s.start_ns for s in spans)
    t_max = max(s.end_ns for s in spans)
    total_ns = max(1, t_max - t_min)

    # Build parent -> children tree
    by_id = {s.span_id: s for s in spans}
    children_map: dict[str | None, list[Span]] = {}
    for s in spans:
        pid = s.parent_span_id if s.parent_span_id in by_id else None
        children_map.setdefault(pid, []).append(s)

    # Sort siblings by start time
    for pid in children_map:
        children_map[pid].sort(key=lambda s: s.start_ns)

    ordered_spans: list[tuple[Span, int, str]] = []

    def traverse(pid: str | None, depth: int, prefix: str) -> None:
        children = children_map.get(pid, [])
        for i, child in enumerate(children):
            is_last = (i == len(children) - 1)
            connector = "└─ " if is_last else "├─ "
            current_prefix = prefix + connector if depth > 0 else ""
            ordered_spans.append((child, depth, current_prefix))
            next_prefix = prefix + ("   " if is_last else "│  ") if depth > 0 else " "
            traverse(child.span_id, depth + 1, next_prefix)

    traverse(None, 0, "")

    for span, depth, prefix in ordered_spans:
        # Calculate bar coordinates
        start_rel = (span.start_ns - t_min) / total_ns
        end_rel = (span.end_ns - t_min) / total_ns

        pos_start = min(bar_width - 1, max(0, int(start_rel * bar_width)))
        pos_end = min(bar_width, max(pos_start + 1, int(end_rel * bar_width)))

        bar_text = Text()
        bar_text.append(" " * pos_start)

        # Style by SpanKind
        color = "cyan"
        if span.kind == SpanKind.LLM:
            color = "bright_blue"
        elif span.kind == SpanKind.TOOL:
            color = "magenta"
        elif span.kind == SpanKind.AGENT:
            color = "green"

        if span.first_token_ns and span.first_token_ns > span.start_ns:
            ttft_rel = min(end_rel, max(start_rel, (span.first_token_ns - t_min) / total_ns))
            pos_ttft = min(pos_end, max(pos_start, int(ttft_rel * bar_width)))
            ttft_len = max(1, pos_ttft - pos_start) if pos_ttft > pos_start else 0
            gen_len = max(0, pos_end - (pos_start + ttft_len))

            bar_text.append("░" * ttft_len, style="yellow")
            bar_text.append("█" * gen_len, style=color)
        else:
            bar_text.append("█" * (pos_end - pos_start), style=color)

        trailing_spaces = max(0, bar_width - pos_end)
        bar_text.append(" " * trailing_spaces)

        name_display = f"{prefix}{span.name}"
        ttft_str = _fmt_duration(span.ttft_ms) if span.ttft_ms is not None else "—"
        cost_str = _fmt_cost(span.cost)

        table.add_row(
            name_display,
            bar_text,
            _fmt_duration(span.duration_ms),
            ttft_str,
            cost_str,
        )

    return table


def render_terminal_report(
    result: AnalysisResult,
    source: str = "trace",
    spans: list[Span] | None = None,
) -> str:
    """Render analysis results to a rich terminal report with Gantt waterfall."""
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=True, width=80)

    # --- Summary ---
    summary_text = (
        f"Total spans: {result.total_spans}    "
        f"Total cost: {_fmt_cost(result.total_cost)}\n"
        f"Wall-clock: {_fmt_duration(result.wall_clock_ms)}   "
        f"Compute time: {_fmt_duration(result.compute_time_ms)}"
    )
    console.print(Panel(summary_text, title=f"[bold]Spandrift Analysis: {source}[/bold]"))

    # --- Per-Agent Rollup ---
    if result.rollup.height > 0:
        table = Table(title="Per-Agent Rollup", show_lines=False)
        table.add_column("Agent", style="cyan")
        table.add_column("Cost", justify="right")
        table.add_column("Wall-clock", justify="right")
        table.add_column("Compute", justify="right")
        table.add_column("LLM calls", justify="right")
        table.add_column("Tokens (in/out)", justify="right")

        for row in result.rollup.iter_rows(named=True):
            agent = row.get("agent_name", "?")
            cost = _fmt_cost(row.get("total_cost"))
            wall = _fmt_duration(row.get("wall_clock_ms", 0))
            compute = _fmt_duration(row.get("compute_time_ms", 0))
            llm = str(row.get("llm_calls", 0))
            tok_in = _fmt_tokens(row.get("total_input_tokens", 0))
            tok_out = _fmt_tokens(row.get("total_output_tokens", 0))
            table.add_row(agent, cost, wall, compute, llm, f"{tok_in}/{tok_out}")

        console.print(table)

    # --- Waterfall / Gantt Chart ---
    if spans:
        console.print()
        console.print(render_waterfall_table(spans))

    # --- Duplicates ---
    if result.duplicates.height > 0:
        console.print()
        console.print("[bold yellow]⚠ Duplicate Calls[/bold yellow]")
        for row in result.duplicates.iter_rows(named=True):
            agent = row.get("agent_name", "?")
            count = row.get("call_count", 0)
            hash_prefix = (row.get("input_hash") or "?")[:7]
            waste = _fmt_cost(row.get("estimated_waste"))
            console.print(
                f"  {agent} called {count}× with identical input "
                f"(hash: {hash_prefix})  wasted: {waste}"
            )

    # --- Retry Storms ---
    if result.retry_storms:
        console.print()
        console.print("[bold yellow]⚠ Retry/Loop Storms[/bold yellow]")
        for storm in result.retry_storms:
            chain = " → ".join(storm.span_ids[:4])
            if len(storm.span_ids) > 4:
                chain += " → …"
            if storm.similarity < 1.0:
                sim_str = f"near-identical input ({storm.similarity:.0%} similarity)"
            else:
                sim_str = "identical input"
            console.print(
                f"  {storm.agent_or_tool}: {storm.chain_length} calls "
                f"with {sim_str} (chain: {chain})"
            )

    # --- TTFT / Latency Outliers ---
    if result.ttft_outliers.height > 0:
        console.print()
        console.print("[bold yellow]⚠ Latency / TTFT Outliers[/bold yellow]")
        for row in result.ttft_outliers.iter_rows(named=True):
            model = row.get("model", "?")
            span_id = (row.get("span_id") or "?")[:8]
            metric = (row.get("metric") or "latency").upper()
            lat = _fmt_duration(row.get("latency_ms", 0))
            p95 = _fmt_duration(row.get("p95_ms", 0))
            ratio = row.get("ratio", 0)
            console.print(
                f"  {model} span {span_id} [{metric}]: {lat} "
                f"(p95 = {p95}, {ratio:.1f}× baseline)"
            )

    # --- No issues ---
    if (
        result.duplicates.height == 0
        and not result.retry_storms
        and result.ttft_outliers.height == 0
    ):
        console.print()
        console.print("[bold green]✓ No issues detected[/bold green]")

    return buffer.getvalue()


def render_html_report(
    result: AnalysisResult,
    source: str = "trace",
    spans: list[Span] | None = None,
) -> str:
    """Render analysis results as a self-contained HTML file."""
    parts: list[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append("<html><head>")
    parts.append(f"<title>Spandrift Analysis: {html.escape(source)}</title>")
    parts.append("<style>")
    parts.append("""
        body { font-family: 'Segoe UI', system-ui, sans-serif; max-width: 960px;
               margin: 2em auto; padding: 0 1em; color: #1a1a1a;
               background: #fafafa; }
        h1 { color: #2563eb; border-bottom: 2px solid #2563eb; padding-bottom: 0.3em; }
        h2 { color: #374151; margin-top: 1.5em; }
        table { border-collapse: collapse; width: 100%; margin: 1em 0; }
        th { background: #2563eb; color: white; padding: 0.6em 1em;
             text-align: left; font-weight: 600; }
        td { padding: 0.5em 1em; border-bottom: 1px solid #e5e7eb; }
        tr:hover { background: #f0f4ff; }
        .metric { display: inline-block; background: #e0e7ff; padding: 0.4em 0.8em;
                  border-radius: 6px; margin: 0.3em; font-size: 0.95em; }
        .warn { background: #fef3c7; border-left: 4px solid #f59e0b;
                padding: 0.8em 1em; margin: 1em 0; border-radius: 4px; }
        .ok { background: #d1fae5; border-left: 4px solid #10b981;
              padding: 0.8em 1em; margin: 1em 0; border-radius: 4px; }
        code { background: #f3f4f6; padding: 0.15em 0.4em; border-radius: 3px;
               font-size: 0.9em; }
        .gantt-bar-bg { background: #e5e7eb; height: 14px; border-radius: 3px; position: relative; width: 100%; min-width: 140px; }
        .gantt-bar { position: absolute; height: 100%; border-radius: 3px; background: #2563eb; }
        .gantt-ttft { position: absolute; height: 100%; background: #f59e0b; border-radius: 3px 0 0 3px; }
    """)
    parts.append("</style></head><body>")
    parts.append(f"<h1>Spandrift Analysis: {html.escape(source)}</h1>")

    # Summary
    parts.append("<div>")
    parts.append(f'<span class="metric">Spans: {result.total_spans}</span>')
    parts.append(f'<span class="metric">Cost: {_fmt_cost(result.total_cost)}</span>')
    parts.append(
        f'<span class="metric">Wall-clock: {_fmt_duration(result.wall_clock_ms)}</span>'
    )
    parts.append(
        f'<span class="metric">Compute: {_fmt_duration(result.compute_time_ms)}</span>'
    )
    parts.append("</div>")

    # Rollup table
    if result.rollup.height > 0:
        parts.append("<h2>Per-Agent Rollup</h2>")
        parts.append("<table><tr>")
        parts.append(
            "<th>Agent</th><th>Cost</th><th>Wall-clock</th>"
            "<th>Compute</th><th>LLM calls</th><th>Tokens (in/out)</th>"
        )
        parts.append("</tr>")
        for row in result.rollup.iter_rows(named=True):
            agent = html.escape(row.get("agent_name", "?"))
            cost = _fmt_cost(row.get("total_cost"))
            wall = _fmt_duration(row.get("wall_clock_ms", 0))
            compute = _fmt_duration(row.get("compute_time_ms", 0))
            llm = row.get("llm_calls", 0)
            tok_in = _fmt_tokens(row.get("total_input_tokens", 0))
            tok_out = _fmt_tokens(row.get("total_output_tokens", 0))
            parts.append(
                f"<tr><td>{agent}</td><td>{cost}</td><td>{wall}</td>"
                f"<td>{compute}</td><td>{llm}</td><td>{tok_in}/{tok_out}</td></tr>"
            )
        parts.append("</table>")

    # HTML Waterfall Gantt
    if spans:
        t_min = min(s.start_ns for s in spans)
        t_max = max(s.end_ns for s in spans)
        total_ns = max(1, t_max - t_min)

        parts.append("<h2>Execution Waterfall & Concurrency</h2>")
        parts.append("<table><tr>")
        parts.append("<th>Task / Span</th><th>Timeline</th><th>Duration</th><th>TTFT</th><th>Cost</th></tr>")

        for s in spans:
            left_pct = ((s.start_ns - t_min) / total_ns) * 100
            width_pct = max(1.0, ((s.end_ns - s.start_ns) / total_ns) * 100)

            ttft_html = ""
            if s.first_token_ns and s.first_token_ns > s.start_ns:
                ttft_w = min(100.0, ((s.first_token_ns - s.start_ns) / max(1, s.end_ns - s.start_ns)) * 100)
                ttft_html = f'<div class="gantt-ttft" style="width:{ttft_w:.1f}%;"></div>'

            bar_color = "#10b981" if s.kind == SpanKind.AGENT else ("#2563eb" if s.kind == SpanKind.LLM else "#8b5cf6")
            bar_elem = (
                f'<div class="gantt-bar-bg">'
                f'<div class="gantt-bar" style="left:{left_pct:.1f}%;width:{width_pct:.1f}%;background:{bar_color};">'
                f'{ttft_html}</div></div>'
            )

            name = html.escape(s.name)
            dur = _fmt_duration(s.duration_ms)
            ttft = _fmt_duration(s.ttft_ms) if s.ttft_ms is not None else "—"
            cost = _fmt_cost(s.cost)

            parts.append(
                f"<tr><td><code>{name}</code></td><td>{bar_elem}</td>"
                f"<td>{dur}</td><td>{ttft}</td><td>{cost}</td></tr>"
            )
        parts.append("</table>")

    # Duplicates
    if result.duplicates.height > 0:
        parts.append('<h2>⚠ Duplicate Calls</h2>')
        for row in result.duplicates.iter_rows(named=True):
            agent = html.escape(row.get("agent_name", "?"))
            count = row.get("call_count", 0)
            hash_prefix = (row.get("input_hash") or "?")[:7]
            waste = _fmt_cost(row.get("estimated_waste"))
            parts.append(
                f'<div class="warn">{agent} called {count}× with identical input '
                f"(hash: <code>{hash_prefix}</code>)  wasted: {waste}</div>"
            )

    # Retry storms
    if result.retry_storms:
        parts.append('<h2>⚠ Retry/Loop Storms</h2>')
        for storm in result.retry_storms:
            chain = " → ".join(s[:8] for s in storm.span_ids[:4])
            if storm.similarity < 1.0:
                sim_str = f"near-identical input ({storm.similarity:.0%} similarity)"
            else:
                sim_str = "identical input"
            parts.append(
                f'<div class="warn">{html.escape(storm.agent_or_tool)}: '
                f"{storm.chain_length} calls with {sim_str} "
                f"(chain: <code>{chain}</code>)</div>"
            )

    # TTFT / Latency outliers
    if result.ttft_outliers.height > 0:
        parts.append("<h2>⚠ Latency / TTFT Outliers</h2>")
        parts.append("<table><tr>")
        parts.append("<th>Model</th><th>Span</th><th>Metric</th><th>Latency</th><th>p95</th><th>Ratio</th>")
        parts.append("</tr>")
        for row in result.ttft_outliers.iter_rows(named=True):
            model = html.escape(row.get("model", "?"))
            span_id = (row.get("span_id") or "?")[:8]
            metric = html.escape((row.get("metric") or "latency").upper())
            lat = _fmt_duration(row.get("latency_ms", 0))
            p95 = _fmt_duration(row.get("p95_ms", 0))
            ratio = row.get("ratio", 0)
            parts.append(
                f"<tr><td>{model}</td><td><code>{span_id}</code></td><td>{metric}</td>"
                f"<td>{lat}</td><td>{p95}</td><td>{ratio:.1f}×</td></tr>"
            )
        parts.append("</table>")

    if (
        result.duplicates.height == 0
        and not result.retry_storms
        and result.ttft_outliers.height == 0
    ):
        parts.append('<div class="ok">✓ No issues detected</div>')

    parts.append("</body></html>")
    return "\n".join(parts)


def save_html_report(
    result: AnalysisResult,
    path: str | Path,
    source: str = "trace",
    spans: list[Span] | None = None,
) -> None:
    """Write the HTML report to a file."""
    content = render_html_report(result, source, spans=spans)
    Path(path).write_text(content, encoding="utf-8")
