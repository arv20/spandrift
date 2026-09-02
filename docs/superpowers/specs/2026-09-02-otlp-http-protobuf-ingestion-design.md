# OTLP/HTTP Protobuf Ingestion Design

## Objective

Allow `spandrift listen` to receive standard OTLP/HTTP protobuf trace exports at `/v1/traces` while retaining OTLP/HTTP JSON ingestion and routing both wire formats through Spandrift's existing normalized `Span` model, cost enrichment, analysis, reporting, and persistence pipeline.

## Existing Architecture

`OTLPTraceHandler.do_POST` currently reads the request body, rejects `application/x-protobuf`, decodes all other bodies as JSON, traverses `resourceSpans` and `scopeSpans`, and calls `_parse_raw_span` for each span. `_parse_raw_span` flattens OTLP `AnyValue` JSON objects, normalizes trace metadata and GenAI/OpenInference semantic attributes, and returns the common immutable `Span` dataclass consumed by enrichment and analysis.

The current JSON traversal discards resource attributes and instrumentation-scope metadata before `_parse_raw_span` is called. The `Span` model does not represent events, so event preservation is outside this change's compatibility boundary.

## Dependency

Add `opentelemetry-proto` as the sole new runtime dependency. It supplies the official generated `ExportTraceServiceRequest`, `ExportTraceServiceResponse`, and OTLP data-model message classes. It depends on the protobuf runtime but does not pull in the OpenTelemetry API, SDK, exporter, or collector.

Add `opentelemetry-exporter-otlp-proto-http` only to the development dependency group so the real-exporter compatibility test is reproducible. The existing development dependencies already install the OpenTelemetry SDK.

## Architecture and Data Flow

The request path will be:

1. Parse the `Content-Type` header into a normalized, lowercase MIME type while ignoring valid parameters.
2. Dispatch `application/json` to the JSON decoder and `application/x-protobuf` to the protobuf decoder. Reject all other types with HTTP 415.
3. Convert either decoded request to one common OTLP envelope made of mappings and lists using the JSON field names already understood by `_parse_raw_span`.
4. Traverse resource spans and scope spans in one shared `parse_otlp_spans` function.
5. Call the existing `_parse_raw_span` for each normalized raw span.
6. Enrich, analyze, save, and report the resulting `Span` objects through the unchanged server pipeline.

The protobuf decoder will be isolated in the ingestion module. It will not call generic protobuf JSON conversion because generic conversion renders `bytes` fields as base64; OTLP JSON and Spandrift expect trace and span IDs as hexadecimal strings.

## Protobuf Normalization

The decoder will parse the body as `ExportTraceServiceRequest` and recursively convert official protobuf messages into the common OTLP mapping:

- `trace_id`, `span_id`, and non-empty `parent_span_id` byte strings become lowercase, zero-preserving hexadecimal strings via `bytes.hex()`.
- Span names, numeric kinds, nanosecond timestamps, status code, and status message map directly to their OTLP JSON equivalents.
- `AnyValue` uses protobuf oneof inspection so strings, booleans, signed integers, doubles, byte strings, arrays, and key-value lists retain their type. Byte-valued attributes will remain bytes because Spandrift's custom-attribute field accepts arbitrary Python values.
- Resource attributes and instrumentation-scope attributes use the same `AnyValue` conversion.
- Empty parent IDs become `None` through the existing raw-span normalizer.

The `Span` dataclass will gain defaulted, backward-compatible fields for `resource_attributes`, `scope_name`, `scope_version`, and `scope_attributes`. The shared envelope traversal will populate these fields for both JSON and protobuf requests. Keeping resource and scope data separate prevents key collisions with span attributes and preserves OTLP's namespaces. Existing constructors and analyzers remain valid because the fields have defaults and analysis continues to consume span-level attributes.

Events will not be added to `Span` in this change. The existing Spandrift model and analyzers do not support them, and the requirement limits event conversion to where the current model supports it.

## HTTP Behavior

- Accept `application/json` and `application/x-protobuf`, including parameters such as `charset=utf-8`.
- Return HTTP 200 with an empty successful `ExportTraceServiceResponse` encoded in the request's wire format: `{}` for JSON and the official serialized protobuf response for protobuf.
- Return HTTP 400 with a short JSON error for malformed JSON, malformed protobuf, invalid `Content-Length`, or an empty request body under the receiver's existing policy.
- Return HTTP 415 with a short JSON error for unsupported or missing media types.
- Do not return exception text or stack traces. Log detailed exceptions server-side at debug level where useful.
- Set an explicit response `Content-Type` and `Content-Length` on all handled responses.

## Tests

Receiver tests will use a server bound to an ephemeral port and real HTTP requests. Protobuf fixtures will be constructed with official generated OTLP classes. Tests will prove:

- Existing JSON ingestion still produces analyzed normalized spans.
- A serialized `ExportTraceServiceRequest` succeeds and returns a parseable `ExportTraceServiceResponse`.
- Multiple spans, parent-child IDs, timestamps, kinds, status, resource metadata, scope metadata, and string/int/bool/double attributes survive decoding.
- Array and key-value-list values are recursively preserved.
- Raw ID bytes become exact lowercase, zero-preserving hex strings.
- Protobuf content types with parameters are accepted.
- Malformed protobuf and malformed JSON return 400 without internal details.
- Unsupported media types return 415.
- Existing server, ingest, analysis, diff, CLI, profiler, adapter, and cost tests remain green.

An integration test will launch the receiver and run a fresh Python subprocess containing the standard `TracerProvider`, `BatchSpanProcessor`, and `OTLPSpanExporter` flow. The subprocess boundary avoids pollution from OpenTelemetry's process-global tracer provider. The test will assert successful shutdown/export and verify that the received `research_agent` and `llm_call` spans retain their parent-child relationship and can be passed through Spandrift analysis.

## Documentation

Update the README and `listen` command help to identify `http://127.0.0.1:4318/v1/traces` as the trace endpoint, state support for OTLP/HTTP protobuf and JSON, show the standard Python HTTP exporter example without forcing `http/json`, and remove the current protocol-forcing guidance.

## Validation

Run the focused tests during each red-green-refactor cycle, then the full pytest suite. Run configured formatting, lint, and type checks if the repository defines them. Finally, start a real receiver, export nested spans with the standard Python OTLP HTTP exporter using its default protobuf protocol, verify there is no HTTP 415, and analyze the received trace.

## Compatibility

No CLI command names or options change. JSON request ingestion remains supported through the same span normalizer. The new `Span` fields are optional and appended with defaults. `analyze`, `diff`, JSON file ingestion, profiler ingestion, reports, and cost enrichment keep their existing interfaces.
