# spandrift

Local-first, OpenTelemetry-native trace analyzer for multi-agent LLM systems: catches redundant calls, retry storms, and cost regressions, and gates CI on them.

```
╭──────────────────── Spandrift Analysis: head_trace.json ─────────────────────╮
│ Total spans: 15    Total cost: $0.0152                                       │
│ Wall-clock: 234ms   Compute time: 775ms                                      │
╰──────────────────────────────────────────────────────────────────────────────╯
                      Execution Waterfall & Concurrency
 Span / Task         Timeline (░=TTFT, █=Exec)     Duration  TTFT       Cost
 Orchestrator        ████████████████████████████     234ms     —          —
  ├─ ResearchAgent   ████████                          74ms     —          —
  │  ├─ chat gpt-4o    ░░░██                           42ms  21ms  $0.003400
  │  └─ web_search          █                          11ms     —          —
  ├─ FactChecker     ██████████                        85ms     —          —
  │  ├─ chat gpt-4o   ░░██                             31ms  21ms  $0.002075
  │  ├─ web_search        █                            11ms     —          —
  │  ├─ web_search         █                           10ms     —          —
  │  ├─ web_search          █                          11ms     —          —
  │  └─ web_search           ██                        11ms     —          —
  ├─ ResearchAgent             █████████               75ms     —          —
  │  ├─ chat gpt-4o              ░░░██                 42ms  21ms  $0.003400
  │  └─ web_search                    ██               11ms     —          —
  └─ WriterAgent                        ████████       74ms     —          —
     └─ chat gpt-4o                       ░░░░██       52ms  31ms  $0.006325

⚠ Duplicate Calls
  ResearchAgent called 2× with identical input  wasted: $0.003400

⚠ Retry/Loop Storms
  web_search: 4 calls with identical input
```

This is **not** a new observability platform. Frameworks like smolagents and Pydantic AI already emit standard OpenTelemetry spans; tools like Phoenix, Langfuse, and Logfire already do general tracing well. Spandrift consumes those standard spans and focuses on diagnostics specific to multi-agent orchestration that general-purpose backends don't foreground.

## Quickstart

```bash
pip install spandrift
spandrift analyze trace.json
```

Generate an HTML report:
```bash
spandrift analyze trace.json --html report.html
```

---

## What It Catches

- **Duplicate calls**: same agent called with the exact same input multiple times, with recursive subtree cost rollup showing wasted spend.
- **Retry / loop storms**: identical or near-identical calls in sequence (fuzzy Jaccard matching on raw inputs, not just exact hash).
- **Latency & TTFT outliers**: per-model outlier detection on Time-to-First-Token or total duration.
- **Cost regressions between runs**: `spandrift diff base.json head.json` compares per-agent cost and latency, exits non-zero when thresholds are exceeded.

## CLI Commands

### `spandrift analyze`

```bash
spandrift analyze trace.json                          # terminal report
spandrift analyze trace.json --html report.html       # + HTML report
```

### `spandrift diff`

```bash
spandrift diff base.json head.json --cost-threshold 0.10 --latency-threshold 0.20 --exit-code
```

Exits `1` if any agent's cost increases >10% or latency >20%. Designed for CI gating.

### `spandrift listen` (optional convenience)

Starts a loopback-only HTTP receiver for OTLP JSON trace exports:

```bash
spandrift listen --port 4318 --save-dir traces/
```

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:4318"
export OTEL_EXPORTER_OTLP_PROTOCOL="http/json"
python my_multi_agent_app.py
```

Binds to `127.0.0.1` by default. Use `--host 0.0.0.0` to accept remote connections.

---

## Python API

For custom async orchestration that isn't auto-instrumented by OTel:

```python
import asyncio
from spandrift.profiler import profile_agent, profile_tool, collect_trace, mark_first_token
from spandrift.models import SpanKind

@profile_tool(name="database_lookup")
async def db_lookup(query: str):
    return await run_query(query)

@profile_agent(name="SearchAgent")
async def search(query: str):
    await db_lookup(query)
    return "done"

@profile_agent(name="Orchestrator")
async def main():
    await asyncio.gather(search("topic A"), search("topic B"))

async def run():
    async with collect_trace() as spans:
        await main()
    # spans is a list of Span objects with correct parent/child attribution
    # even across concurrent asyncio.gather branches
```

For streaming, call `mark_first_token()` when the first chunk arrives to capture real TTFT:

```python
from spandrift.profiler import span_scope, mark_first_token

async with span_scope("chat gpt-4o", kind=SpanKind.LLM, model="gpt-4o"):
    async for chunk in stream_response():
        if is_first_chunk:
            mark_first_token()
```

---

## GitHub Actions

Use the reusable action or the CLI directly:

```yaml
name: Spandrift CI Gate
on:
  pull_request:
    branches: [main]

permissions:
  pull-requests: write  # only needed if you want PR comments

jobs:
  trace-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install spandrift
      - run: python demo/run_demo.py  # or your own benchmark
      - run: |
          spandrift diff \
            demo/base_trace.json demo/head_trace.json \
            --cost-threshold 0.10 --latency-threshold 0.20 \
            --exit-code
```

---

## Known Trade-offs

- **Detection coverage on spans without captured inputs**: Duplicate and retry-storm detection require `input.value` or `gen_ai.input.messages` attributes on the span (or exact input hashes). Spans lacking input telemetry (such as bare LLM spans from minimal OTel instrumentation) are never treated as matches and will not be flagged. The `@profile_agent` decorator path automatically captures raw inputs.
- **Pricing is a static rate table** in `cost_engine.py`, verified as of 2026-08-19. Override with `SPANDRIFT_PRICES_PATH="custom_prices.json"` for new models or negotiated rates. [genai-prices](https://github.com/pydantic/genai-prices) is a compatible alternative backend for v2.
- **The LangChain/LangGraph callback handler** (`spandrift.adapters.SpandriftCallbackHandler`) is experimental and untested against real LangChain runs. LangSmith is the first-party option there.

---

## License

MIT — see [LICENSE](LICENSE).
