"""Tests for the OTLP ingestion HTTP server."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

import pytest
from google.protobuf import json_format
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)
from opentelemetry.proto.common.v1.common_pb2 import (
    AnyValue,
    ArrayValue,
    InstrumentationScope,
    KeyValue,
    KeyValueList,
)
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import (
    ResourceSpans,
    ScopeSpans,
    Span as OTLPSpan,
    Status,
)

from spandrift.analysis import analyze
from spandrift.ingest import export_otlp_json
from spandrift.models import Span, SpanKind
from spandrift.server import OTLPTraceServer, start_otlp_server


@pytest.fixture
def otlp_server() -> Iterator[OTLPTraceServer]:
    server = start_otlp_server(host="127.0.0.1", port=0, auto_analyze=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _url(server: OTLPTraceServer, path: str) -> str:
    return f"http://127.0.0.1:{server.server_port}{path}"


def _post(
    server: OTLPTraceServer,
    body: bytes,
    content_type: str,
) -> tuple[int, str, bytes]:
    request = urllib.request.Request(
        _url(server, "/v1/traces"),
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return (
                response.status,
                response.headers.get_content_type(),
                response.read(),
            )
    except urllib.error.HTTPError as error:
        return error.code, error.headers.get_content_type(), error.read()


def _key_value(key: str, **value: Any) -> KeyValue:
    return KeyValue(key=key, value=AnyValue(**value))


def _protobuf_request() -> ExportTraceServiceRequest:
    trace_id = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
    parent_span_id = bytes.fromhex("0001020304050607")
    child_span_id = bytes.fromhex("08090a0b0c0d0e0f")

    root = OTLPSpan(
        trace_id=trace_id,
        span_id=parent_span_id,
        name="research_agent",
        kind=1,
        start_time_unix_nano=1_000_000_000,
        end_time_unix_nano=3_000_000_000,
        attributes=[
            _key_value("string.attr", string_value="value"),
            _key_value("int.attr", int_value=42),
            _key_value("bool.attr", bool_value=True),
            _key_value("double.attr", double_value=2.5),
            _key_value(
                "array.attr",
                array_value=ArrayValue(
                    values=[AnyValue(string_value="first"), AnyValue(int_value=2)]
                ),
            ),
            _key_value(
                "map.attr",
                kvlist_value=KeyValueList(
                    values=[_key_value("nested", bool_value=False)]
                ),
            ),
        ],
        status=Status(code=1),
    )
    child = OTLPSpan(
        trace_id=trace_id,
        span_id=child_span_id,
        parent_span_id=parent_span_id,
        name="llm_call",
        kind=3,
        start_time_unix_nano=1_500_000_000,
        end_time_unix_nano=2_500_000_000,
        attributes=[
            _key_value("gen_ai.operation.name", string_value="chat"),
            _key_value("gen_ai.request.model", string_value="gpt-4o"),
        ],
        status=Status(code=2, message="provider error"),
    )

    return ExportTraceServiceRequest(
        resource_spans=[
            ResourceSpans(
                resource=Resource(
                    attributes=[
                        _key_value("service.name", string_value="research-service"),
                        _key_value("replicas", int_value=3),
                    ]
                ),
                scope_spans=[
                    ScopeSpans(
                        scope=InstrumentationScope(
                            name="spandrift-test",
                            version="1.2.3",
                            attributes=[_key_value("scope.attr", bool_value=True)],
                        ),
                        spans=[root, child],
                    )
                ],
            )
        ]
    )


def test_otlp_server_health(otlp_server: OTLPTraceServer) -> None:
    with urllib.request.urlopen(_url(otlp_server, "/health"), timeout=5) as response:
        assert response.status == 200
        assert json.loads(response.read()) == {
            "status": "ok",
            "service": "spandrift-otlp-receiver",
        }


def test_json_ingestion_remains_supported(otlp_server: OTLPTraceServer) -> None:
    spans = [
        Span(
            trace_id="00000000000000000000000000000001",
            span_id="0000000000000001",
            parent_span_id=None,
            name="AgentA",
            kind=SpanKind.AGENT,
            agent_name="AgentA",
            start_ns=1_000_000_000,
            end_ns=2_000_000_000,
        )
    ]
    payload = json.dumps(export_otlp_json(spans)).encode()

    status, content_type, response_body = _post(
        otlp_server,
        payload,
        "application/json; charset=utf-8",
    )

    assert status == 200
    assert content_type == "application/json"
    json_format.Parse(response_body, ExportTraceServiceResponse())
    assert len(otlp_server.received_traces) == 1
    assert otlp_server.received_traces[0][0].name == "AgentA"


def test_protobuf_ingestion_preserves_otlp_data(
    otlp_server: OTLPTraceServer,
) -> None:
    request = _protobuf_request()

    status, content_type, response_body = _post(
        otlp_server,
        request.SerializeToString(),
        "application/x-protobuf",
    )

    assert status == 200
    assert content_type == "application/x-protobuf"
    assert (
        ExportTraceServiceResponse.FromString(response_body)
        == ExportTraceServiceResponse()
    )

    assert len(otlp_server.received_traces) == 1
    received = otlp_server.received_traces[0]
    assert len(received) == 2
    by_name = {span.name: span for span in received}
    root = by_name["research_agent"]
    child = by_name["llm_call"]

    assert root.trace_id == "000102030405060708090a0b0c0d0e0f"
    assert root.span_id == "0001020304050607"
    assert root.parent_span_id is None
    assert child.trace_id == root.trace_id
    assert child.span_id == "08090a0b0c0d0e0f"
    assert child.parent_span_id == root.span_id
    assert root.start_ns == 1_000_000_000
    assert root.end_ns == 3_000_000_000
    assert child.kind == SpanKind.LLM
    assert child.status_code == 2
    assert child.status_message == "provider error"

    assert root.attributes["string.attr"] == "value"
    assert root.attributes["int.attr"] == 42
    assert root.attributes["bool.attr"] is True
    assert root.attributes["double.attr"] == 2.5
    assert root.attributes["array.attr"] == ["first", 2]
    assert root.attributes["map.attr"] == {"nested": False}
    assert root.resource_attributes == {
        "service.name": "research-service",
        "replicas": 3,
    }
    assert root.scope_name == "spandrift-test"
    assert root.scope_version == "1.2.3"
    assert root.scope_attributes == {"scope.attr": True}
    assert analyze(received).total_spans == 2


def test_protobuf_content_type_parameters_are_accepted(
    otlp_server: OTLPTraceServer,
) -> None:
    status, content_type, response_body = _post(
        otlp_server,
        _protobuf_request().SerializeToString(),
        "application/x-protobuf; charset=utf-8",
    )

    assert status == 200
    assert content_type == "application/x-protobuf"
    ExportTraceServiceResponse.FromString(response_body)
    assert len(otlp_server.received_traces) == 1


def test_invalid_protobuf_returns_sanitized_400(
    otlp_server: OTLPTraceServer,
) -> None:
    status, content_type, response_body = _post(
        otlp_server,
        b"\x0a\x05abc",
        "application/x-protobuf",
    )

    assert status == 400
    assert content_type == "application/json"
    response = json.loads(response_body)
    assert response == {"error": "Invalid protobuf payload"}
    assert "Traceback" not in response_body.decode()
    assert otlp_server.received_traces == []


def test_invalid_json_returns_sanitized_400(otlp_server: OTLPTraceServer) -> None:
    status, content_type, response_body = _post(
        otlp_server,
        b'{"resourceSpans":',
        "application/json",
    )

    assert status == 400
    assert content_type == "application/json"
    assert json.loads(response_body) == {"error": "Invalid JSON payload"}
    assert otlp_server.received_traces == []


def test_unsupported_content_type_returns_415(
    otlp_server: OTLPTraceServer,
) -> None:
    status, content_type, response_body = _post(
        otlp_server,
        b"not an OTLP request",
        "text/plain",
    )

    assert status == 415
    assert content_type == "application/json"
    assert json.loads(response_body) == {"error": "Unsupported Media Type"}
    assert otlp_server.received_traces == []


def test_standard_python_otlp_http_exporter_works_without_protocol_override(
    otlp_server: OTLPTraceServer,
) -> None:
    script = textwrap.dedent(
        f"""
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider = TracerProvider()
        trace.set_tracer_provider(provider)

        exporter = OTLPSpanExporter(
            endpoint="{_url(otlp_server, '/v1/traces')}"
        )

        provider.add_span_processor(BatchSpanProcessor(exporter))

        tracer = trace.get_tracer("spandrift-test")

        with tracer.start_as_current_span("research_agent"):
            with tracer.start_as_current_span("llm_call"):
                pass

        provider.shutdown()
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Failed to export" not in completed.stderr
    assert len(otlp_server.received_traces) == 1
    received = otlp_server.received_traces[0]
    by_name = {span.name: span for span in received}
    assert by_name["llm_call"].parent_span_id == by_name["research_agent"].span_id
    assert analyze(received).total_spans == 2
