"""Ingest spans from OTLP JSON exports and OTel SDK in-memory exporters.

Two mapping tables handle attribute normalisation:

* **OTel GenAI** — covers Pydantic AI and standard `gen_ai.*` semantic
  conventions.
* **OpenInference** — covers smolagents and other Phoenix-instrumented
  libraries that emit `openinference.span.kind`, `llm.token_count.*`, etc.

The format is auto-detected per-span based on attribute keys.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from spandrift.models import Span, SpanKind

# ---------------------------------------------------------------------------
# OTel span-kind int → fallback SpanKind
# ---------------------------------------------------------------------------

_OTEL_KIND_MAP: dict[int, SpanKind] = {
    1: SpanKind.INTERNAL,  # INTERNAL
    2: SpanKind.INTERNAL,  # SERVER
    3: SpanKind.LLM,       # CLIENT — most GenAI spans are client calls
    4: SpanKind.INTERNAL,  # PRODUCER
    5: SpanKind.INTERNAL,  # CONSUMER
}

# ---------------------------------------------------------------------------
# OTel GenAI operation.name → SpanKind
# ---------------------------------------------------------------------------

_GENAI_OP_KIND: dict[str, SpanKind] = {
    "chat": SpanKind.LLM,
    "invoke_agent": SpanKind.AGENT,
    "execute_tool": SpanKind.TOOL,
}

# ---------------------------------------------------------------------------
# OpenInference span kind string → SpanKind
# ---------------------------------------------------------------------------

_OI_KIND_MAP: dict[str, SpanKind] = {
    "AGENT": SpanKind.AGENT,
    "LLM": SpanKind.LLM,
    "TOOL": SpanKind.TOOL,
    "CHAIN": SpanKind.CHAIN,
}


# ===================================================================
# OTLP typed-value flattening
# ===================================================================

def _flatten_value(val: dict[str, Any]) -> Any:
    """Flatten a single OTLP typed attribute value to a Python native.

    Examples:
        >>> _flatten_value({"stringValue": "hello"})
        'hello'
        >>> _flatten_value({"intValue": "150"})
        150
    """
    if "stringValue" in val:
        return val["stringValue"]
    if "intValue" in val:
        return int(val["intValue"])
    if "doubleValue" in val:
        return float(val["doubleValue"])
    if "boolValue" in val:
        return bool(val["boolValue"])
    if "arrayValue" in val:
        return [_flatten_value(v) for v in val["arrayValue"].get("values", [])]
    if "kvlistValue" in val:
        return {
            p["key"]: _flatten_value(p["value"])
            for p in val["kvlistValue"].get("values", [])
        }
    # Unknown type — return as-is so nothing is silently dropped.
    return val


def _flatten_attributes(attrs: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert the OTLP attribute list into a flat Python dict."""
    return {a["key"]: _flatten_value(a["value"]) for a in attrs}


# ===================================================================
# Format auto-detection
# ===================================================================

_OI_PREFIXES = ("openinference.", "llm.token_count")


def _is_openinference(attrs: dict[str, Any]) -> bool:
    """Return True when the attribute dict looks like OpenInference data."""
    return any(k.startswith(_OI_PREFIXES) for k in attrs)


# ===================================================================
# Input-hash computation
# ===================================================================

def _hash_input(raw: Any) -> str:
    """SHA-256 prefix (16 hex chars) of the JSON-serialised input."""
    if isinstance(raw, str):
        payload = raw
    else:
        payload = json.dumps(raw, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ===================================================================
# Mapping helpers
# ===================================================================

def _map_genai(
    attrs: dict[str, Any],
    otel_kind_int: int,
) -> dict[str, Any]:
    """Extract Span field overrides from OTel GenAI semantic conventions."""
    out: dict[str, Any] = {}

    # Token counts
    if (v := attrs.get("gen_ai.usage.input_tokens")) is not None:
        out["input_tokens"] = int(v)
    elif (v := attrs.get("gen_ai.usage.prompt_tokens")) is not None:
        out["input_tokens"] = int(v)

    if (v := attrs.get("gen_ai.usage.output_tokens")) is not None:
        out["output_tokens"] = int(v)
    elif (v := attrs.get("gen_ai.usage.completion_tokens")) is not None:
        out["output_tokens"] = int(v)

    # Prompt Cache Read Tokens
    for k in (
        "gen_ai.usage.cache_read.input_tokens",
        "gen_ai.usage.cache_read_input_tokens",
        "openai.prompt_tokens_details.cached_tokens",
        "anthropic.cache_read_input_tokens",
        "deepseek.prompt_cache_hit_tokens",
    ):
        if (v := attrs.get(k)) is not None:
            out["cache_read_tokens"] = int(v)
            break

    # Prompt Cache Creation / Write Tokens
    for k in (
        "gen_ai.usage.cache_creation.input_tokens",
        "gen_ai.usage.cache_creation_input_tokens",
        "anthropic.cache_creation_input_tokens",
        "gen_ai.usage.cache_write.input_tokens",
    ):
        if (v := attrs.get(k)) is not None:
            out["cache_write_tokens"] = int(v)
            break

    # Model — prefer response.model over request.model
    if (v := attrs.get("gen_ai.request.model")) is not None:
        out["model"] = str(v)
    if (v := attrs.get("gen_ai.response.model")) is not None:
        out["model"] = str(v)

    # Provider — gen_ai.provider.name takes precedence over gen_ai.system
    if (v := attrs.get("gen_ai.system")) is not None:
        out["provider"] = str(v)
    if (v := attrs.get("gen_ai.provider.name")) is not None:
        out["provider"] = str(v)

    # Operation / agent
    if (v := attrs.get("gen_ai.operation.name")) is not None:
        out["operation"] = str(v)
    if (v := attrs.get("gen_ai.agent.name")) is not None:
        out["agent_name"] = str(v)

    # Kind inference
    op = attrs.get("gen_ai.operation.name")
    if op and str(op) in _GENAI_OP_KIND:
        out["kind"] = _GENAI_OP_KIND[str(op)]
    else:
        out["kind"] = _OTEL_KIND_MAP.get(otel_kind_int, SpanKind.INTERNAL)

    # Input hash from gen_ai.input.messages
    if (v := attrs.get("gen_ai.input.messages")) is not None:
        out["input_hash"] = _hash_input(v)
        out["input_value"] = str(v) if not isinstance(v, str) else v

    # TTFT / first token timestamp
    for key in (
        "gen_ai.response.time_to_first_chunk",
        "gen_ai.server.time_to_first_token",
        "gen_ai.response.first_token_ns",
        "first_token_ns",
    ):
        if (v := attrs.get(key)) is not None:
            try:
                val = float(v)
                # If val is an absolute ns timestamp (e.g. > 1e15)
                if val > 1e15:
                    out["first_token_ns"] = int(val)
                # If val is in seconds duration (e.g. 0.35s)
                elif val < 1000:
                    start = int(attrs.get("startTimeUnixNano", 0))
                    # will be resolved with start_ns in caller if needed
                    out["_ttft_duration_s"] = val
                else:
                    out["first_token_ns"] = int(val)
                break
            except (ValueError, TypeError):
                pass

    return out


def _map_openinference(
    attrs: dict[str, Any],
    otel_kind_int: int,
    span_name: str,
) -> dict[str, Any]:
    """Extract Span field overrides from OpenInference semantic conventions."""
    out: dict[str, Any] = {}

    # Token counts — try naming variants
    for key in ("llm.token_count.prompt", "llm.token_count.prompt_tokens"):
        if (v := attrs.get(key)) is not None:
            out["input_tokens"] = int(v)
            break
    for key in ("llm.token_count.completion", "llm.token_count.completion_tokens"):
        if (v := attrs.get(key)) is not None:
            out["output_tokens"] = int(v)
            break

    # Cache read/write
    for key in (
        "llm.token_count.prompt_tokens_details.cached_tokens",
        "llm.token_count.cache_read",
        "llm.token_count.cache_read_tokens",
    ):
        if (v := attrs.get(key)) is not None:
            out["cache_read_tokens"] = int(v)
            break
    for key in (
        "llm.token_count.cache_write",
        "llm.token_count.cache_creation_tokens",
        "llm.token_count.cache_write_tokens",
    ):
        if (v := attrs.get(key)) is not None:
            out["cache_write_tokens"] = int(v)
            break

    # Model
    if (v := attrs.get("llm.model_name")) is not None:
        out["model"] = str(v)

    # Kind
    oi_kind = attrs.get("openinference.span.kind")
    if oi_kind and str(oi_kind).upper() in _OI_KIND_MAP:
        out["kind"] = _OI_KIND_MAP[str(oi_kind).upper()]
    else:
        out["kind"] = _OTEL_KIND_MAP.get(otel_kind_int, SpanKind.INTERNAL)

    # Tool spans: override name with tool.name if available
    if (v := attrs.get("tool.name")) is not None:
        out["name"] = str(v)

    # Input hash from input.value
    if (v := attrs.get("input.value")) is not None:
        out["input_hash"] = _hash_input(v)
        out["input_value"] = str(v) if not isinstance(v, str) else v

    # TTFT / first token timestamp
    for key in (
        "llm.time_to_first_token",
        "llm.time_to_first_token_ms",
        "time_to_first_token",
        "first_token_ns",
    ):
        if (v := attrs.get(key)) is not None:
            try:
                val = float(v)
                if val > 1e15:
                    out["first_token_ns"] = int(val)
                elif val < 1000:
                    out["_ttft_duration_s"] = val
                else:
                    out["_ttft_duration_s"] = val / 1000.0
                break
            except (ValueError, TypeError):
                pass

    return out


# ===================================================================
# OTLP JSON loading
# ===================================================================

def _hex_id(raw: str) -> str:
    """Normalise a hex-encoded trace/span id (lower-case, stripped)."""
    return raw.strip().lower()


def _parse_raw_span(raw: dict[str, Any]) -> Span:
    """Convert a single raw OTLP JSON span dict into a normalised Span."""
    raw_attrs: list[dict[str, Any]] = raw.get("attributes", [])
    attrs = _flatten_attributes(raw_attrs)

    otel_kind_int: int = raw.get("kind", 0)
    span_name: str = raw.get("name", "")

    # Auto-detect mapping format
    if _is_openinference(attrs):
        mapped = _map_openinference(attrs, otel_kind_int, span_name)
    else:
        mapped = _map_genai(attrs, otel_kind_int)

    kind: SpanKind = mapped.pop("kind", SpanKind.INTERNAL)
    name: str = mapped.pop("name", span_name)

    start_ns = int(raw.get("startTimeUnixNano", 0))
    end_ns = int(raw.get("endTimeUnixNano", 0))

    if "_ttft_duration_s" in mapped:
        offset_ns = int(mapped.pop("_ttft_duration_s") * 1_000_000_000)
        mapped["first_token_ns"] = start_ns + offset_ns

    # Status
    status = raw.get("status", {})
    status_code = int(status.get("code", 0))
    status_message: str | None = status.get("message") or None

    return Span(
        trace_id=_hex_id(raw.get("traceId", "")),
        span_id=_hex_id(raw.get("spanId", "")),
        parent_span_id=_hex_id(raw["parentSpanId"]) if raw.get("parentSpanId") else None,
        name=name,
        kind=kind,
        start_ns=start_ns,
        end_ns=end_ns,
        status_code=status_code,
        status_message=status_message,
        attributes=attrs,
        **{k: v for k, v in mapped.items()},
    )


def load_otlp_json(path: str | Path) -> list[Span]:
    """Read an OTLP JSON export file and return normalised spans.

    Args:
        path: Filesystem path to the JSON file.  Accepts the standard
            ``{"resourceSpans": [...]}`` envelope.

    Returns:
        A list of :class:`Span` objects, one per raw span found in the file.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    spans: list[Span] = []
    for rs in data.get("resourceSpans", []):
        for ss in rs.get("scopeSpans", []):
            for raw in ss.get("spans", []):
                spans.append(_parse_raw_span(raw))
    return spans


# ===================================================================
# Convenience wrapper
# ===================================================================

def load_spans(path: str | Path) -> list[Span]:
    """Load spans from a file, auto-detecting format.

    Currently only OTLP JSON is supported.  Future versions may sniff
    CSV / Parquet / etc.

    Args:
        path: Filesystem path to the span data file.

    Returns:
        A list of normalised :class:`Span` objects.
    """
    return load_otlp_json(path)


# ===================================================================
# OTel SDK in-memory span conversion
# ===================================================================

def _readable_span_attrs(span: Any) -> dict[str, Any]:
    """Extract an attribute dict from a ReadableSpan, handling None."""
    raw = span.attributes
    if raw is None:
        return {}
    # ReadableSpan.attributes is already a dict-like mapping.
    return dict(raw)


def _format_trace_id(trace_id: int) -> str:
    """Format an OTel SDK integer trace id as a 32-char lower-hex string."""
    return f"{trace_id:032x}"


def _format_span_id(span_id: int) -> str:
    """Format an OTel SDK integer span id as a 16-char lower-hex string."""
    return f"{span_id:016x}"


def spans_from_otel_sdk(spans: list[Any]) -> list[Span]:
    """Convert OTel SDK ReadableSpan objects into normalised Spans.

    This is useful when collecting spans via
    :class:`opentelemetry.sdk.trace.export.in_memory_span_exporter.InMemorySpanExporter`.

    Args:
        spans: A list of ``ReadableSpan`` instances (or compatible objects).

    Returns:
        A list of normalised :class:`Span` objects.
    """
    result: list[Span] = []
    for s in spans:
        attrs = _readable_span_attrs(s)

        # OTel SDK uses IntEnum for kind; .value gives the int
        otel_kind_int = int(s.kind.value) if hasattr(s.kind, "value") else int(s.kind)
        span_name: str = s.name

        if _is_openinference(attrs):
            mapped = _map_openinference(attrs, otel_kind_int, span_name)
        else:
            mapped = _map_genai(attrs, otel_kind_int)

        kind: SpanKind = mapped.pop("kind", SpanKind.INTERNAL)
        name: str = mapped.pop("name", span_name)

        start_ns = s.start_time
        end_ns = s.end_time

        if "_ttft_duration_s" in mapped:
            offset_ns = int(mapped.pop("_ttft_duration_s") * 1_000_000_000)
            mapped["first_token_ns"] = start_ns + offset_ns

        # Parent span id
        parent_span_id: str | None = None
        if s.parent is not None:
            parent_span_id = _format_span_id(s.parent.span_id)

        # Status
        status_code = 0
        status_message: str | None = None
        if s.status is not None:
            status_code = int(
                s.status.status_code.value
                if hasattr(s.status.status_code, "value")
                else s.status.status_code
            )
            status_message = s.status.description or None

        result.append(
            Span(
                trace_id=_format_trace_id(s.context.trace_id),
                span_id=_format_span_id(s.context.span_id),
                parent_span_id=parent_span_id,
                name=name,
                kind=kind,
                start_ns=start_ns,
                end_ns=end_ns,
                status_code=status_code,
                status_message=status_message,
                attributes=attrs,
                **{k: v for k, v in mapped.items()},
            )
        )
    return result


# ===================================================================
# OTLP JSON export
# ===================================================================

def export_otlp_json(spans: list[Span]) -> dict[str, Any]:
    """Convert a list of normalized Span objects into standard OTLP JSON structure."""
    otlp_spans: list[dict[str, Any]] = []

    for s in spans:
        attrs: list[dict[str, Any]] = []
        if s.operation:
            attrs.append({"key": "gen_ai.operation.name", "value": {"stringValue": s.operation}})
        if s.agent_name:
            attrs.append({"key": "gen_ai.agent.name", "value": {"stringValue": s.agent_name}})
        if s.model:
            attrs.append({"key": "gen_ai.request.model", "value": {"stringValue": s.model}})
            attrs.append({"key": "gen_ai.response.model", "value": {"stringValue": s.model}})
        if s.provider:
            attrs.append({"key": "gen_ai.provider.name", "value": {"stringValue": s.provider}})
        if s.input_tokens:
            attrs.append({"key": "gen_ai.usage.input_tokens", "value": {"intValue": str(s.input_tokens)}})
        if s.output_tokens:
            attrs.append({"key": "gen_ai.usage.output_tokens", "value": {"intValue": str(s.output_tokens)}})
        if s.cache_read_tokens:
            attrs.append({"key": "gen_ai.usage.cache_read.input_tokens", "value": {"intValue": str(s.cache_read_tokens)}})
        if s.cache_write_tokens:
            attrs.append({"key": "gen_ai.usage.cache_creation.input_tokens", "value": {"intValue": str(s.cache_write_tokens)}})
        if s.first_token_ns and s.first_token_ns > s.start_ns:
            ttft_s = (s.first_token_ns - s.start_ns) / 1_000_000_000
            attrs.append({"key": "gen_ai.response.time_to_first_chunk", "value": {"doubleValue": ttft_s}})
        if s.input_value:
            attrs.append({"key": "input.value", "value": {"stringValue": s.input_value}})
            attrs.append({"key": "gen_ai.input.messages", "value": {"stringValue": s.input_value}})
        # When input_value is absent, do NOT substitute input_hash into
        # input.value — on re-ingestion the hash would be treated as real
        # input text, re-hashed into a different digest, and fed to Jaccard
        # similarity as meaningless tokens.

        # Include custom attributes
        for k, v in s.attributes.items():
            if not any(a["key"] == k for a in attrs):
                if isinstance(v, bool):
                    attrs.append({"key": k, "value": {"boolValue": v}})
                elif isinstance(v, int):
                    attrs.append({"key": k, "value": {"intValue": str(v)}})
                elif isinstance(v, float):
                    attrs.append({"key": k, "value": {"doubleValue": v}})
                elif isinstance(v, list):
                    attrs.append({"key": k, "value": {"arrayValue": {"values": [{"stringValue": str(item)} for item in v]}}})
                else:
                    attrs.append({"key": k, "value": {"stringValue": str(v)}})

        kind_int = 3 if s.kind == SpanKind.LLM else (1 if s.kind in (SpanKind.AGENT, SpanKind.TOOL) else 1)

        raw_span: dict[str, Any] = {
            "traceId": s.trace_id,
            "spanId": s.span_id,
            "name": s.name,
            "kind": kind_int,
            "startTimeUnixNano": str(s.start_ns),
            "endTimeUnixNano": str(s.end_ns),
            "attributes": attrs,
            "status": {"code": s.status_code},
        }
        if s.parent_span_id:
            raw_span["parentSpanId"] = s.parent_span_id

        otlp_spans.append(raw_span)

    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "spandrift-demo"}},
                        {"key": "telemetry.sdk.language", "value": {"stringValue": "python"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "spandrift.profiler", "version": "0.1.0"},
                        "spans": otlp_spans,
                    }
                ],
            }
        ]
    }


def save_otlp_json(spans: list[Span], path: str | Path) -> None:
    """Save a list of normalized Span objects as an OTLP JSON file."""
    data = export_otlp_json(spans)
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
