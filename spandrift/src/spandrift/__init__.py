"""spandrift — multi-agent LLM trace analysis."""

from __future__ import annotations

from spandrift.adapters import (
    trace_agent,
    trace_llm,
    trace_tool,
)
from spandrift.analysis import AnalysisResult, analyze
from spandrift.cost_engine import compute_cost, enrich_spans
from spandrift.diff import DiffResult, compute_diff
from spandrift.ingest import load_otlp_json, load_spans, save_otlp_json
from spandrift.models import Span, SpanKind
from spandrift.profiler import (
    collect_trace,
    get_current_span,
    mark_first_token,
    profile_agent,
    profile_tool,
    span_scope,
)

__version__ = "0.1.0"

__all__ = [
    "AnalysisResult",
    "DiffResult",
    "Span",
    "SpanKind",
    "analyze",
    "collect_trace",
    "compute_cost",
    "compute_diff",
    "enrich_spans",
    "get_current_span",
    "load_otlp_json",
    "load_spans",
    "mark_first_token",
    "profile_agent",
    "profile_tool",
    "save_otlp_json",
    "span_scope",
    "trace_agent",
    "trace_llm",
    "trace_tool",
]
