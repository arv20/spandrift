"""Lightweight in-process HTTP OTLP Ingestion Server.

Listens for standard OpenTelemetry OTLP JSON HTTP trace exports on /v1/traces
(default port: 4318). Compatible with any OpenTelemetry SDK:
    OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:4318"
    OTEL_EXPORTER_OTLP_PROTOCOL="http/json"
"""

from __future__ import annotations

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from spandrift.analysis import AnalysisResult, analyze
from spandrift.cost_engine import enrich_spans
from spandrift.ingest import _parse_raw_span, save_otlp_json
from spandrift.models import Span
from spandrift.report import render_terminal_report

logger = logging.getLogger(__name__)


class OTLPTraceHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for OTLP /v1/traces endpoints."""

    server: OTLPTraceServer  # type: ignore[assignment]

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP request logging unless debug is enabled."""
        if logger.isEnabledFor(logging.DEBUG):
            super().log_message(format, *args)

    def do_GET(self) -> None:
        """Health check endpoint."""
        if self.path in ("/", "/health", "/v1/traces"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok", "service": "spandrift-otlp-receiver"}')
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        """Handle incoming OTLP JSON trace export."""
        if not self.path.startswith("/v1/traces"):
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error": "Empty body"}')
            return

        body = self.rfile.read(content_length)
        content_type = self.headers.get("Content-Type", "")

        # Check if client accidentally sent binary protobuf
        if "application/x-protobuf" in content_type:
            self.send_response(415)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            err_msg = {
                "error": "Unsupported Media Type: Spandrift receiver accepts HTTP/JSON.",
                "hint": "Set export OTEL_EXPORTER_OTLP_PROTOCOL='http/json' in your client environment.",
            }
            self.wfile.write(json.dumps(err_msg).encode())
            return

        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            err_msg = {
                "error": f"Invalid JSON payload: {e}",
                "hint": "Ensure your OpenTelemetry exporter uses JSON: OTEL_EXPORTER_OTLP_PROTOCOL='http/json'",
            }
            self.wfile.write(json.dumps(err_msg).encode())
            return

        # Parse spans from OTLP structure
        spans: list[Span] = []
        for rs in payload.get("resourceSpans", []):
            for ss in rs.get("scopeSpans", []):
                for raw in ss.get("spans", []):
                    spans.append(_parse_raw_span(raw))

        if spans:
            enriched = enrich_spans(spans)
            self.server.handle_received_spans(enriched)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps({"status": "ok", "spans_received": len(spans)}).encode()
        )


class OTLPTraceServer(ThreadingHTTPServer):
    """Multi-threaded HTTP Server for OTLP traces."""

    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        on_trace: Callable[[list[Span], AnalysisResult], None] | None = None,
        save_dir: Path | None = None,
        auto_analyze: bool = True,
    ) -> None:
        super().__init__(server_address, OTLPTraceHandler)
        self.on_trace = on_trace
        self.save_dir = save_dir
        self.auto_analyze = auto_analyze
        self.received_traces: list[list[Span]] = []

        if self.save_dir:
            self.save_dir.mkdir(parents=True, exist_ok=True)

    def handle_received_spans(self, spans: list[Span]) -> None:
        """Process a received batch of spans."""
        self.received_traces.append(spans)
        result = analyze(spans)

        if self.save_dir:
            trace_id = spans[0].trace_id if spans else f"trace_{int(time.time())}"
            filepath = self.save_dir / f"{trace_id}.json"
            save_otlp_json(spans, filepath)

        if self.auto_analyze:
            trace_id = (spans[0].trace_id[:8] if spans else "trace")
            report = render_terminal_report(result, source=f"Live OTLP [{trace_id}]", spans=spans)
            print("\n" + report)

        if self.on_trace:
            self.on_trace(spans, result)


def start_otlp_server(
    host: str = "127.0.0.1",
    port: int = 4318,
    *,
    save_dir: str | Path | None = None,
    auto_analyze: bool = True,
    on_trace: Callable[[list[Span], AnalysisResult], None] | None = None,
) -> OTLPTraceServer:
    """Start an OTLP ingestion server in the current or background thread."""
    save_path = Path(save_dir) if save_dir else None
    server = OTLPTraceServer(
        (host, port),
        on_trace=on_trace,
        save_dir=save_path,
        auto_analyze=auto_analyze,
    )
    return server
