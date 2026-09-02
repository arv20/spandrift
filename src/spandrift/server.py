"""Lightweight in-process HTTP OTLP ingestion server.

Listens for OTLP/HTTP protobuf and JSON trace exports on /v1/traces
(default port: 4318).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from google.protobuf.message import DecodeError
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceResponse,
)

from spandrift.analysis import AnalysisResult, analyze
from spandrift.cost_engine import enrich_spans
from spandrift.ingest import decode_otlp_protobuf, parse_otlp_spans, save_otlp_json
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
        """Handle an OTLP/HTTP JSON or protobuf trace export."""
        if not self.path.startswith("/v1/traces"):
            self.send_response(404)
            self.end_headers()
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            self._send_json_error(400, "Invalid Content-Length")
            return

        if content_length <= 0:
            self._send_json_error(400, "Empty body")
            return

        content_type = self.headers.get_content_type().lower()
        if content_type not in {"application/json", "application/x-protobuf"}:
            self._send_json_error(415, "Unsupported Media Type")
            return

        body = self.rfile.read(content_length)
        try:
            if content_type == "application/x-protobuf":
                payload = decode_otlp_protobuf(body)
            else:
                payload = json.loads(body.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("OTLP JSON request must be an object")
            spans = parse_otlp_spans(payload)
        except DecodeError:
            logger.debug("Invalid OTLP protobuf payload", exc_info=True)
            self._send_json_error(400, "Invalid protobuf payload")
            return
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
            KeyError,
        ):
            logger.debug("Invalid OTLP JSON payload", exc_info=True)
            self._send_json_error(400, "Invalid JSON payload")
            return

        if spans:
            enriched = enrich_spans(spans)
            self.server.handle_received_spans(enriched)

        if content_type == "application/x-protobuf":
            response_body = ExportTraceServiceResponse().SerializeToString()
        else:
            response_body = b"{}"
        self._send_body(200, content_type, response_body)

    def _send_json_error(self, status: int, message: str) -> None:
        """Send a sanitized JSON error response."""
        self._send_body(
            status,
            "application/json",
            json.dumps({"error": message}).encode("utf-8"),
        )

    def _send_body(self, status: int, content_type: str, body: bytes) -> None:
        """Send a complete HTTP response with explicit representation headers."""
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


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
