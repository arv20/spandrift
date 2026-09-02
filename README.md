# spandrift

Local-first trace analysis for multi-agent LLM systems.

Basically, spandrift reads the OpenTelemetry spans your agents are probably already producing and tries to answer a few questions that normal tracing dashboards don't really focus on:

- which agent actually cost the money?
- did the same tool/agent accidentally get called twice?
- are retries going crazy?
- did this PR make the workflow slower or more expensive?

It's not meant to replace Langfuse, Phoenix, Logfire, etc. If you're already sending traces to one of those, keep doing that.

spandrift just reads the same OTel spans and runs a smaller set of checks that are more specific to agent workflows.

Right now it works with spans from `openinference-instrumentation-smolagents` for smolagents, Pydantic AI's built-in instrumentation, and its own decorators for code that isn't instrumented already.

## Install

```bash
pip install spandrift
```

Python 3.11+ is required.

The concurrency-safe attribution stuff depends on `asyncio.TaskGroup` and the `context=` argument on `create_task`, which were both added in 3.11.

## Quickstart

```bash
spandrift analyze demo/trace.json
```

```text
╭──────────────────── Spandrift Analysis: head_trace.json ─────────────────────╮
│ Total spans: 15    Total cost: $0.0152                                       │
│ Wall-clock: 234ms   Compute time: 775ms                                      │
╰──────────────────────────────────────────────────────────────────────────────╯
                                Per-Agent Rollup
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃               ┃           ┃            ┃         ┃           ┃        Tokens ┃
┃ Agent         ┃      Cost ┃ Wall-clock ┃ Compute ┃ LLM calls ┃      (in/out) ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ FactChecker   │ $0.002075 │       85ms │   159ms │         1 │       350/120 │
│ Orchestrator  │ $0.000000 │      234ms │   234ms │         0 │           0/0 │
│ ResearchAgent │ $0.006800 │      149ms │   255ms │         2 │      1.0k/420 │
│ WriterAgent   │ $0.006325 │       74ms │   126ms │         1 │       850/420 │
└───────────────┴───────────┴────────────┴─────────┴───────────┴───────────────┘

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

You can also compare two runs:

```bash
spandrift diff base.json head.json --cost-threshold 0.10 --exit-code
```

That makes it usable in CI too. If the cost delta crosses the threshold, the command can fail the step.

There's a composite GitHub Action in `action.yml` that wraps this. If you want it to post the diff as a PR comment, the calling workflow needs:

```yaml
pull-requests: write
```

There's also:

```bash
spandrift listen
```

which starts a local OTLP receiver so you don't have to write a trace file first. It binds to `127.0.0.1` by default.

## What it catches

### Cost + latency per agent

Costs and timing are rolled up per agent, including workflows with concurrent branches.

This matters because if two sub-agents run at the same time through `asyncio.gather`, you obviously don't want to just add both wall-clock durations together and pretend they ran sequentially.

### Duplicate calls

If the same agent or tool gets called twice with the same input in one run, it'll flag it.

This has caught more dumb orchestration bugs than I expected.

### Retry storms

It also looks for repeated calls with identical or near-identical input.

Those get chained using exact matches or token-level similarity on the captured input text, so something retrying over and over with tiny changes doesn't just disappear into the trace.

### TTFT outliers

TTFT = time to first token.

spandrift tracks that separately from total request duration and flags outliers per model. Mostly useful for figuring out whether the actual agent got slower or whether a provider/model was just having a bad time.

## How it works

For code that isn't already OTel-instrumented, there are two decorators:

```python
@profile_agent
@profile_tool
```

They wrap async functions and emit spans in the same general shape as the other supported instrumentation.

A surprisingly annoying part of building this was getting attribution right with concurrency.

A global "current span" works fine until two agents run at the same time. Then child spans can start getting attributed to whichever agent most recently changed the global value, which is obviously bad.

spandrift uses `contextvars.ContextVar` instead.

asyncio copies context when tasks are created, so each concurrent task keeps the right agent context without having to manually pass IDs everywhere.

There's a test specifically for this too: two agents execute concurrently and both produce child spans. I wanted a test that would actually break the naive implementation instead of just testing the easy sequential case.

The analysis side uses Polars.

Most of the work is grouped batch aggregation anyway — cost by agent, latency percentiles by model, retries, duplicates, etc. A run can also get into the thousands of spans pretty quickly once agents start retrying, so using a columnar dataframe library made sense.

## A bug I found while building it

The cost calculation ended up being slightly more annoying than expected because of cached tokens.

OpenTelemetry's:

```text
gen_ai.usage.input_tokens
```

is the total input token count, including cached input.

So if you take that value and then add cache-read/cache-write token counts separately, you're double-counting part of the bill.

I originally did exactly that.

I caught it by comparing spandrift's numbers against `genai-prices` on a few actual Anthropic/OpenAI caching scenarios. The fix is in `cost_engine.py` and there's a regression test for it now.

## Known trade-offs

Duplicate/retry detection needs the input text to actually exist in the span.

Usually that's either:

```text
input.value
```

or:

```text
gen_ai.input.messages
```

The `@profile_agent` path always captures it, but bare LLM spans from really minimal OTel instrumentation sometimes don't.

If the input isn't there, spandrift doesn't try to guess. That span just isn't checked for duplicate/retry similarity.

Pricing is also a static table right now, not a live API lookup.

`cost_engine.py` includes the date the bundled prices were last verified. If something changes before I update it, you can override the table with:

```bash
SPANDRIFT_PRICES_PATH
```

There's also a LangChain/LangGraph adapter under `spandrift.adapters`.

That part is experimental and definitely less tested than the core path. Also, if your entire stack is LangChain, LangSmith already does a lot, so I'm not trying to pretend this replaces it.

## Why I made this

I mostly wanted something I could run locally on traces after changing an agent workflow and immediately answer stuff like:

> why did this run suddenly cost 40% more?

or

> why did this tool execute 6 times?

General observability tools are way more capable overall, but sometimes I just want those answers without digging through a tracing UI.

That's basically the point of spandrift.

It's still a young project, so issues and PRs are very welcome. If something looks wrong, there's a non-zero chance it actually is.

## License

MIT © Aarav Kolgaonkar
