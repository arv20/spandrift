"""Tests for CLI commands (analyze and diff)."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
import pytest

from spandrift.cli import main


def make_sample_trace_json(tmp_path: Path, name: str, cost_multiplier: float = 1.0) -> Path:
    payload = {
        "resourceSpans": [
            {
                "resource": {"attributes": []},
                "scopeSpans": [
                    {
                        "scope": {"name": "opentelemetry.instrumentation.genai"},
                        "spans": [
                            {
                                "traceId": "trace123",
                                "spanId": "span1",
                                "name": "invoke_agent Orchestrator",
                                "kind": 1,
                                "startTimeUnixNano": "1700000000000000000",
                                "endTimeUnixNano": "1700000002000000000",
                                "attributes": [
                                    {"key": "gen_ai.operation.name", "value": {"stringValue": "invoke_agent"}},
                                    {"key": "gen_ai.agent.name", "value": {"stringValue": "Orchestrator"}},
                                ],
                            },
                            {
                                "traceId": "trace123",
                                "spanId": "span2",
                                "parentSpanId": "span1",
                                "name": "chat gpt-4o",
                                "kind": 3,
                                "startTimeUnixNano": "1700000000200000000",
                                "endTimeUnixNano": "1700000001800000000",
                                "attributes": [
                                    {"key": "gen_ai.provider.name", "value": {"stringValue": "openai"}},
                                    {"key": "gen_ai.operation.name", "value": {"stringValue": "chat"}},
                                    {"key": "gen_ai.request.model", "value": {"stringValue": "gpt-4o"}},
                                    {"key": "gen_ai.usage.input_tokens", "value": {"intValue": str(int(1000 * cost_multiplier))}},
                                    {"key": "gen_ai.usage.output_tokens", "value": {"intValue": str(int(500 * cost_multiplier))}},
                                ],
                            },
                        ],
                    }
                ],
            }
        ]
    }
    p = tmp_path / name
    p.write_text(json.dumps(payload))
    return p


def test_cli_analyze(tmp_path: Path):
    trace_file = make_sample_trace_json(tmp_path, "trace.json")
    html_file = tmp_path / "report.html"

    runner = CliRunner()
    result = runner.invoke(main, ["analyze", str(trace_file), "--html", str(html_file)])

    assert result.exit_code == 0
    assert "Spandrift Analysis" in result.output
    assert "Orchestrator" in result.output
    assert html_file.exists()
    assert "Spandrift Analysis: trace.json" in html_file.read_text()


def test_cli_diff_pass(tmp_path: Path):
    base_file = make_sample_trace_json(tmp_path, "base.json", cost_multiplier=1.0)
    head_file = make_sample_trace_json(tmp_path, "head.json", cost_multiplier=1.05)  # +5%

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["diff", str(base_file), str(head_file), "--cost-threshold", "0.10"],
    )

    assert result.exit_code == 0
    assert "Spandrift Diff" in result.output
    assert "Per-Agent Deltas" in result.output


def test_cli_diff_fail_regression(tmp_path: Path):
    base_file = make_sample_trace_json(tmp_path, "base.json", cost_multiplier=1.0)
    head_file = make_sample_trace_json(tmp_path, "head.json", cost_multiplier=1.50)  # +50% regression

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["diff", str(base_file), str(head_file), "--cost-threshold", "0.10"],
    )

    assert result.exit_code != 0
    assert "Regression exceeds thresholds" in result.output
