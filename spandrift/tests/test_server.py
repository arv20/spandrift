"""Tests for the OTLP Ingestion HTTP Server."""

from __future__ import annotations

import json
import threading
import time
import urllib.request
import urllib.error

import pytest

from spandrift.ingest import export_otlp_json
from spandrift.models import Span, SpanKind
from spandrift.server import start_otlp_server


def test_otlp_server_health_and_ingest():
    # Start server on ephemeral port (e.g. 14318)
    server = start_otlp_server(host="127.0.0.1", port=14318, auto_analyze=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        # 1. Health check
        req = urllib.request.Request("http://127.0.0.1:14318/health")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert data["status"] == "ok"

        # 2. Ingest trace
        spans = [
            Span(
                trace_id="test_trace_1",
                span_id="s1",
                parent_span_id=None,
                name="AgentA",
                kind=SpanKind.AGENT,
                agent_name="AgentA",
                start_ns=1_000_000_000,
                end_ns=2_000_000_000,
            )
        ]
        payload = export_otlp_json(spans)
        req = urllib.request.Request(
            "http://127.0.0.1:14318/v1/traces",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            res = json.loads(resp.read().decode())
            assert res["status"] == "ok"
            assert res["spans_received"] == 1

        assert len(server.received_traces) == 1
        assert server.received_traces[0][0].name == "AgentA"

    finally:
        server.shutdown()
        server.server_close()
