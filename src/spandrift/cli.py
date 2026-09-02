"""CLI entry point — primary interface, no server.

Usage:
    spandrift analyze trace.json [--html output.html]
    spandrift diff base.json head.json [--cost-threshold 0.10] [--latency-threshold 0.20]

A minimal read-only HTTP endpoint could be added later as a stretch goal for
integration with dashboards, but isn't needed for a CLI tool in v1.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click


@click.group()
@click.version_option(package_name="spandrift")
def main() -> None:
    """Analyze execution traces from multi-agent LLM systems."""


@main.command()
@click.argument("trace_file", type=click.Path(exists=True, path_type=Path))
@click.option("--html", "html_path", type=click.Path(path_type=Path), default=None,
              help="Write an HTML report to this file.")
@click.option("--threshold-retries", type=int, default=3,
              help="Minimum chain length to flag as a retry storm.")
def analyze(trace_file: Path, html_path: Path | None, threshold_retries: int) -> None:
    """Analyze a trace file and print a terminal report."""
    from spandrift.analysis import analyze as run_analysis
    from spandrift.cost_engine import enrich_spans
    from spandrift.ingest import load_spans
    from spandrift.report import render_terminal_report, save_html_report

    spans = load_spans(trace_file)
    if not spans:
        click.echo("No spans found in trace file.", err=True)
        sys.exit(1)

    spans = enrich_spans(spans)
    result = run_analysis(spans, retry_threshold=threshold_retries)

    output = render_terminal_report(result, source=trace_file.name, spans=spans)
    click.echo(output)

    if html_path:
        save_html_report(result, html_path, source=trace_file.name, spans=spans)
        click.echo(f"HTML report written to {html_path}")


@main.command()
@click.argument("base_file", type=click.Path(exists=True, path_type=Path))
@click.argument("head_file", type=click.Path(exists=True, path_type=Path))
@click.option("--cost-threshold", type=float, default=0.10,
              help="Cost regression threshold as a fraction (0.10 = 10%).")
@click.option("--latency-threshold", type=float, default=0.20,
              help="Latency regression threshold as a fraction (0.20 = 20%).")
@click.option("--exit-code/--no-exit-code", default=True,
              help="Exit non-zero if thresholds are exceeded (default: True).")
def diff(
    base_file: Path,
    head_file: Path,
    cost_threshold: float,
    latency_threshold: float,
    exit_code: bool,
) -> None:
    """Compare two trace files and report cost/latency deltas."""
    from spandrift.analysis import analyze as run_analysis
    from spandrift.cost_engine import enrich_spans
    from spandrift.diff import check_thresholds, compute_diff, render_diff_report
    from spandrift.ingest import load_spans

    base_spans = enrich_spans(load_spans(base_file))
    head_spans = enrich_spans(load_spans(head_file))

    if not base_spans or not head_spans:
        click.echo("One or both trace files contain no spans.", err=True)
        sys.exit(1)

    base_result = run_analysis(base_spans)
    head_result = run_analysis(head_spans)

    diffs = compute_diff(base_result, head_result)
    output = render_diff_report(
        diffs, base_result, head_result,
        base_source=base_file.name, head_source=head_file.name,
    )
    click.echo(output)

    if exit_code and check_thresholds(diffs, cost_threshold, latency_threshold):
        click.echo(
            f"\n[FAIL] Regression exceeds thresholds "
            f"(cost: {cost_threshold:.0%}, latency: {latency_threshold:.0%})",
            err=True,
        )
        sys.exit(1)


@main.command()
@click.option("--host", default="127.0.0.1", help="Loopback-only by default (127.0.0.1). Use 0.0.0.0 to accept connections from other machines.")
@click.option("--port", "-p", default=4318, type=int, help="Port to listen on (default: 4318).")
@click.option("--save-dir", "-s", type=click.Path(path_type=Path), help="Directory to save received OTLP traces.")
@click.option("--auto-analyze/--no-auto-analyze", default=True, help="Automatically print diagnostic report on trace arrival.")
def listen(host: str, port: int, save_dir: Path | None, auto_analyze: bool) -> None:
    """Start a loopback-only OTLP trace receiver on /v1/traces (default: 127.0.0.1:4318).

    Binds to localhost by default. Use --host 0.0.0.0 to accept remote connections.

    Developers can configure their OpenTelemetry SDK with:
        export OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:4318"
        export OTEL_EXPORTER_OTLP_PROTOCOL="http/json"
    """
    from spandrift.server import start_otlp_server

    server = start_otlp_server(host=host, port=port, save_dir=save_dir, auto_analyze=auto_analyze)
    click.echo(f"📡 Spandrift OTLP receiver listening at http://{host}:{port}/v1/traces")
    if save_dir:
        click.echo(f"📁 Saving incoming traces to: {save_dir}")
    click.echo("Press Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        click.echo("\nStopping OTLP receiver.")
        server.server_close()
