# spandrift

A local-first Python CLI tool that analyzes execution traces from multi-agent LLM systems and flags orchestration-specific problems.

It is **not** a new observability platform. Frameworks like `smolagents` (with `openinference-instrumentation-smolagents`) and `Pydantic AI` already emit standard OpenTelemetry spans, and tools like Phoenix, Langfuse, or Logfire do general tracing and dashboarding well. `spandrift` consumes standard OTel spans and focuses purely on diagnostics specific to multi-agent systems that general-purpose tracing backends don't foreground:

- **Rollup across concurrent branches**: rollup cost and compute without double-counting parallel tasks or inflating non-contiguous agent executions (via interval union).
- **Duplicate call detection**: same agent called with the exact same input multiple times in a single trace, with recursive subtree cost rollups.
- **Fuzzy / semantic retry storms**: catches identical retries and slightly diverging loops (e.g. "Attempt 1: query" vs "Attempt 2: query") using token Jaccard similarity. Fuzzy detection requires raw input strings; for OTLP-ingested traces it works when `input.value` / `gen_ai.input.messages` attributes are present. For the `@profile_agent` decorator path, raw input is always retained automatically.
- **Latency & TTFT outliers**: provider-side slowdowns or Time-to-First-Token degradation per model.
- **Visual execution waterfall**: ASCII/ANSI Gantt chart in the terminal showing parallel fan-outs and TTFT vs generation times.
- **Real-time OTLP receiver**: `spandrift listen` accepts traces from standard OpenTelemetry exporters on localhost (loopback-only by default).
- **CI regression gate & PR Bot**: `spandrift diff` and `action.yml` check cost/latency regressions between runs, post review comments, and gate pull requests.

---

## Why These Design Choices?

### 1. Concurrent Span Attribution via `contextvars.ContextVar`
When sub-agents run concurrently via `asyncio.gather` or `asyncio.TaskGroup`, each task needs to know its parent span. A naive approach that stores the "active span" in a shared module variable fails immediately: Task A sets its span, yields at an `await`, Task B sets its span, and when Task A resumes, its child calls get attributed to Task B.

We use `contextvars.ContextVar` with token-based reset. When `asyncio.create_task()` (or `gather`/`TaskGroup`) spawns a task, CPython captures a shallow copy-on-write snapshot of the caller's context (backed by a HAMT). Mutating `_current_span` in Task A creates a path copy in Task A's trie in $O(1)$ time without modifying Task B's context.

### 2. Columnar Aggregation with Polars
Span analysis is fundamentally batch aggregation: computing grouped metrics (cost per agent, p95 latencies per model, duplicate counts per input hash) over a table of spans. Polars' lazy execution and columnar expressions make these operations concise and fast without maintaining custom grouping loops.

### 3. Ephemeral Cache Token Tiering
Modern agent frameworks rely heavily on prompt caching (Anthropic prompt cache, OpenAI cached prompt tokens, DeepSeek prefix caching). `spandrift` automatically bills uncached prompt tokens at standard rates, cache-read tokens at discounted rates (e.g. 90% discount for Claude, 50% for GPT-4o, 75% for DeepSeek), and cache-write tokens at creation multipliers.

---

## Installation

```bash
pip install spandrift
```

To include optional OpenTelemetry SDK and `smolagents` dependencies:
```bash
pip install "spandrift[otel,smolagents]"
```

---

## CLI Usage

### 1. Analyze a Trace

```bash
spandrift analyze trace.json
```

Generate an optional self-contained HTML report:
```bash
spandrift analyze trace.json --html report.html
```

### 2. Compare Two Runs in CI (`spandrift diff`)

```bash
spandrift diff base.json head.json --cost-threshold 0.10 --latency-threshold 0.20
```
- `--cost-threshold 0.10`: Fail if any agent's cost increases by >10%.
- `--latency-threshold 0.20`: Fail if any agent's latency increases by >20%.
- Exits with returncode `1` if thresholds are exceeded (ideal for GitHub Actions).

### 3. Real-Time OTLP Receiver (`spandrift listen`)

For convenience during development, `spandrift listen` starts a loopback-only
HTTP receiver that accepts standard OTLP JSON trace exports:

```bash
spandrift listen --port 4318 --save-dir traces/
```

Point any OpenTelemetry-instrumented application at it:
```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:4318"
export OTEL_EXPORTER_OTLP_PROTOCOL="http/json"
python my_multi_agent_app.py
```

The listener binds to `127.0.0.1` by default (loopback only). Use `--host 0.0.0.0` to accept connections from other machines.

---

## Real Demo & Actual Terminal Output

The `demo/run_demo.py` script runs a 4-agent workflow (`Orchestrator`, `ResearchAgent`, `FactChecker`, `WriterAgent`) using `smolagents` instrumented with `@profile_agent`. It executes a concurrent fan-out (`asyncio.gather(ResearchAgent, FactChecker)`), a duplicate call to `ResearchAgent`, and a 4-step retry storm in `FactChecker`.

### Output from `spandrift analyze demo/head_trace.json`:

```
╭──────────────────── Spandrift Analysis: head_trace.json ─────────────────────╮
│ Total spans: 15    Total cost: $0.0152                                       │
│ Wall-clock: 235ms   Compute time: 778ms                                      │
╰──────────────────────────────────────────────────────────────────────────────╯
                                Per-Agent Rollup                                
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃               ┃           ┃            ┃         ┃           ┃        Tokens ┃
┃ Agent         ┃      Cost ┃ Wall-clock ┃ Compute ┃ LLM calls ┃      (in/out) ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ FactChecker   │ $0.002075 │       86ms │   160ms │         1 │       350/120 │
│ Orchestrator  │ $0.000000 │      235ms │   235ms │         0 │           0/0 │
│ ResearchAgent │ $0.006800 │      150ms │   256ms │         2 │      1.0k/420 │
│ WriterAgent   │ $0.006325 │       74ms │   126ms │         1 │       850/420 │
└───────────────┴───────────┴────────────┴─────────┴───────────┴───────────────┘

                      Execution Waterfall & Concurrency                      
 Span / Task         Timeline (░=TTFT, █=Exec)     Duration  TTFT       Cost 
 Orchestrator        ████████████████████████████     235ms     —          — 
  ├─ ResearchAgent   ████████                          75ms     —          — 
  │  ├─ chat gpt-4o    ░░░██                           42ms  21ms  $0.003400 
  │  └─ web_search          █                          11ms     —          — 
  ├─ FactChecker     ██████████                        86ms     —          — 
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
  FactChecker called 4× with identical input (hash: 43635ec)  wasted: $0.000000
  ResearchAgent called 2× with identical input (hash: 377f6f9)  wasted: $0.003400
  ResearchAgent called 2× with identical input (hash: bdf540a)  wasted: $0.000000

⚠ Retry/Loop Storms
  chat gpt-4o: 4 calls with identical input (chain: bdcf538c50a44b7f → 002ec832eeef4ddc → 7c745c0f115c4cee → 5e0ba9c7e788497c)
```

### Output from `spandrift diff demo/base_trace.json demo/head_trace.json`:

```
Spandrift Diff: base_trace.json → head_trace.json
Total cost: $0.0118 → $0.0152 (+28.8%)
                                Per-Agent Deltas                                
┏━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┓
┃           ┃     Base ┃           ┃         ┃     Base ┃      Head ┃  Latency ┃
┃ Agent     ┃     Cost ┃ Head Cost ┃  Cost Δ ┃  Latency ┃   Latency ┃        Δ ┃
┡━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━┩
│ FactChec… │ $0.0020… │ $0.002075 │   +0.0% │     53ms │      85ms │   +59.7% │
│ Orchestr… │ $0.0000… │ $0.000000 │   +0.0% │    148ms │     234ms │   +58.2% │
│ Research… │ $0.0034… │ $0.006800 │ +100.0% │     74ms │     149ms │   +99.5% │
│ WriterAg… │ $0.0063… │ $0.006325 │   +0.0% │     73ms │      74ms │    +0.9% │
└───────────┴──────────┴───────────┴─────────┴──────────┴───────────┴──────────┘
```

---

## Python API & Profiling Uninstrumented Code

If you have custom async orchestration functions that aren't auto-instrumented by OTel, wrap them with `@profile_agent` and `@profile_tool`:

```python
import asyncio
from spandrift.profiler import profile_agent, profile_tool, collect_trace, mark_first_token

@profile_tool(name="database_lookup")
async def db_lookup(query: str):
    await asyncio.sleep(0.01)
    return "result"

@profile_agent(name="SearchAgent")
async def search(query: str):
    await db_lookup(query)
    return "done"

@profile_agent(name="Orchestrator")
async def main():
    # Concurrent execution maintains clean span attribution
    await asyncio.gather(search("topic A"), search("topic B"))

async def run():
    async with collect_trace() as spans:
        await main()
    print(f"Collected {len(spans)} spans")
```

For streaming calls, use `mark_first_token()` when the first chunk arrives to measure true Time-to-First-Token (TTFT):

```python
async with span_scope(name="chat gpt-4o", kind=SpanKind.LLM, model="gpt-4o"):
    async for chunk in stream_response():
        if is_first_chunk:
            mark_first_token()
```

---

## GitHub Actions CI Example

A complete workflow configuration is provided in `.github/workflows/ci.yml`:

```yaml
name: Spandrift CI Gate

on:
  pull_request:
    branches: [main]

jobs:
  trace-regression-gate:
    name: Trace Regression Gate (spandrift diff)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install spandrift
        run: pip install -e "."
      - name: Run Benchmark / Generate Traces
        run: python demo/run_demo.py
      - name: Check Cost and Latency Regressions
        run: |
          spandrift diff \
            demo/base_trace.json \
            demo/head_trace.json \
            --cost-threshold 0.10 \
            --latency-threshold 0.20 \
            --exit-code
```

---

## Production Caveats & Edge Cases

To ensure 100% accuracy across diverse production setups, keep these three factors in mind:

| Factor | How It Works | What to Watch Out For |
| :--- | :--- | :--- |
| **1. Upstream Token Telemetry** | Spandrift reads token counts from `gen_ai.usage.*` / `llm.token_count.*` attributes. | If a custom or home-grown LLM wrapper forgets to populate token usage on the span, Spandrift will report cost as `$0.00` or `—`. Standard SDKs (LangChain, OpenAI, LiteLLM, smolagents) populate this automatically. |
| **2. Provider Pricing Drift** | Costs are calculated using a static rate table in `cost_engine.py`, verified as of **2025-06-01**. We evaluated [genai-prices](https://github.com/pydantic/genai-prices) but its `Usage` type does not yet accept cache read/write token counts, which spandrift needs for tiered billing. | For newly launched models, price drops, or enterprise negotiated discounts, supply a custom rate card JSON via `export SPANDRIFT_PRICES_PATH="custom_prices.json"`. See `cost_engine.py` for the expected format. |
| **3. OTLP Protocol Format** | The live receiver (`spandrift listen`) accepts standard HTTP/JSON (`http/json`). | If an OpenTelemetry exporter defaults to streaming binary Protobuf over gRPC to `:4318`, configure it for JSON: `export OTEL_EXPORTER_OTLP_PROTOCOL="http/json"`. |

---

## License

MIT
