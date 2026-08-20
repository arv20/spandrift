# Pricing data should ideally come from an open-source live dataset like
# genai-prices (github.com/pydantic/genai-prices). We evaluated genai-prices
# v0.1.4 for v1, but its Usage API does not yet accept cache_read_tokens or
# cache_write_tokens — it silently drops them — so cache-tiered cost
# calculations cannot be delegated to it today. Once genai-prices supports
# cache token breakdown in its Usage type, this module should switch to it.
#
# Until then, we bundle a static table covering common models with full
# ephemeral cache tiering. Users can extend or override it via the
# SPANDRIFT_PRICES_PATH env var pointing to a JSON file with the same shape.
#
# Prices verified as of: 2025-06-01. If you notice a stale entry, please
# open an issue or PR, or override via SPANDRIFT_PRICES_PATH.

"""Per-span cost computation against a structured tiered pricing table."""

from __future__ import annotations

import dataclasses
import json
import logging
import os
from pathlib import Path
from typing import Any

from spandrift.models import Span, SpanKind

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True, slots=True)
class ModelPricing:
    """Token pricing for a single model variant.

    All monetary values are USD per 1 million tokens.
    """

    input_per_mtok: float  # USD per 1M standard (uncached) input tokens
    output_per_mtok: float  # USD per 1M output tokens
    cache_read_per_mtok: float = 0.0  # USD per 1M cache-read tokens (discounted)
    cache_write_per_mtok: float = 0.0  # USD per 1M cache-write tokens (e.g. Anthropic 1.25x)
    batch_discount: float = 1.0  # multiplier (0.5 = 50% off)


# ---------------------------------------------------------------------------
# Static pricing table — (provider, model) -> ModelPricing
# ---------------------------------------------------------------------------

PRICING_TABLE: dict[tuple[str, str], ModelPricing] = {
    # OpenAI ----------------------------------------------------------------
    ("openai", "gpt-4o"): ModelPricing(
        input_per_mtok=2.50,
        output_per_mtok=10.00,
        cache_read_per_mtok=1.25,  # 50% discount
        batch_discount=0.5,
    ),
    ("openai", "gpt-4o-mini"): ModelPricing(
        input_per_mtok=0.15,
        output_per_mtok=0.60,
        cache_read_per_mtok=0.075,  # 50% discount
        batch_discount=0.5,
    ),
    ("openai", "gpt-4.1"): ModelPricing(
        input_per_mtok=2.00,
        output_per_mtok=8.00,
        cache_read_per_mtok=0.50,
        cache_write_per_mtok=2.00,
    ),
    ("openai", "gpt-4.1-mini"): ModelPricing(
        input_per_mtok=0.40,
        output_per_mtok=1.60,
        cache_read_per_mtok=0.10,
        cache_write_per_mtok=0.40,
    ),
    ("openai", "gpt-4.1-nano"): ModelPricing(
        input_per_mtok=0.10,
        output_per_mtok=0.40,
        cache_read_per_mtok=0.025,
        cache_write_per_mtok=0.10,
    ),
    ("openai", "o1"): ModelPricing(
        input_per_mtok=15.00,
        output_per_mtok=60.00,
        cache_read_per_mtok=7.50,
        batch_discount=0.5,
    ),
    ("openai", "o3"): ModelPricing(
        input_per_mtok=2.00,
        output_per_mtok=8.00,
        cache_read_per_mtok=0.50,
        cache_write_per_mtok=2.00,
    ),
    ("openai", "o3-mini"): ModelPricing(
        input_per_mtok=1.10,
        output_per_mtok=4.40,
        cache_read_per_mtok=0.275,  # 75% discount
        cache_write_per_mtok=1.10,
    ),
    ("openai", "o4-mini"): ModelPricing(
        input_per_mtok=1.10,
        output_per_mtok=4.40,
        cache_read_per_mtok=0.275,
        cache_write_per_mtok=1.10,
    ),
    # Anthropic -------------------------------------------------------------
    ("anthropic", "claude-3-7-sonnet"): ModelPricing(
        input_per_mtok=3.00,
        output_per_mtok=15.00,
        cache_read_per_mtok=0.30,  # 90% discount
        cache_write_per_mtok=3.75,  # 1.25x creation
    ),
    ("anthropic", "claude-3-5-sonnet-20241022"): ModelPricing(
        input_per_mtok=3.00,
        output_per_mtok=15.00,
        cache_read_per_mtok=0.30,  # 90% discount
        cache_write_per_mtok=3.75,  # 1.25x creation
    ),
    ("anthropic", "claude-3-5-sonnet"): ModelPricing(
        input_per_mtok=3.00,
        output_per_mtok=15.00,
        cache_read_per_mtok=0.30,
        cache_write_per_mtok=3.75,
    ),
    ("anthropic", "claude-3-5-haiku-20241022"): ModelPricing(
        input_per_mtok=0.80,
        output_per_mtok=4.00,
        cache_read_per_mtok=0.08,  # 90% discount
        cache_write_per_mtok=1.00,  # 1.25x creation
    ),
    ("anthropic", "claude-3-5-haiku"): ModelPricing(
        input_per_mtok=0.80,
        output_per_mtok=4.00,
        cache_read_per_mtok=0.08,
        cache_write_per_mtok=1.00,
    ),
    ("anthropic", "claude-sonnet-4-20250514"): ModelPricing(
        input_per_mtok=3.00,
        output_per_mtok=15.00,
        cache_read_per_mtok=0.30,
        cache_write_per_mtok=3.75,
    ),
    ("anthropic", "claude-haiku-4-20250514"): ModelPricing(
        input_per_mtok=0.80,
        output_per_mtok=4.00,
        cache_read_per_mtok=0.08,
        cache_write_per_mtok=1.00,
    ),
    # DeepSeek --------------------------------------------------------------
    ("deepseek", "deepseek-chat"): ModelPricing(
        input_per_mtok=0.27,
        output_per_mtok=1.10,
        cache_read_per_mtok=0.07,  # 74% discount
    ),
    ("deepseek", "deepseek-v3"): ModelPricing(
        input_per_mtok=0.27,
        output_per_mtok=1.10,
        cache_read_per_mtok=0.07,
    ),
    ("deepseek", "deepseek-reasoner"): ModelPricing(
        input_per_mtok=0.55,
        output_per_mtok=2.19,
        cache_read_per_mtok=0.14,  # 75% discount
    ),
    ("deepseek", "deepseek-r1"): ModelPricing(
        input_per_mtok=0.55,
        output_per_mtok=2.19,
        cache_read_per_mtok=0.14,
    ),
    # Google ----------------------------------------------------------------
    ("google", "gemini-2.5-pro"): ModelPricing(
        input_per_mtok=1.25,
        output_per_mtok=10.00,
        cache_read_per_mtok=0.3125,
    ),
    ("google", "gemini-2.5-flash"): ModelPricing(
        input_per_mtok=0.15,
        output_per_mtok=0.60,
        cache_read_per_mtok=0.0375,
    ),
    ("google", "gemini-2.0-flash"): ModelPricing(
        input_per_mtok=0.10,
        output_per_mtok=0.40,
        cache_read_per_mtok=0.025,
    ),
}


# ---------------------------------------------------------------------------
# User overrides via SPANDRIFT_PRICES_PATH
# ---------------------------------------------------------------------------

def _load_user_overrides() -> dict[tuple[str, str], ModelPricing]:
    """Load pricing overrides from a user-supplied JSON file."""
    path_str = os.environ.get("SPANDRIFT_PRICES_PATH")
    if not path_str:
        return {}

    path = Path(path_str)
    try:
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load user pricing from %s: %s", path, exc)
        return {}

    overrides: dict[tuple[str, str], ModelPricing] = {}
    for key, fields in raw.items():
        parts = key.split("/", maxsplit=1)
        if len(parts) != 2:
            logger.warning("Skipping malformed pricing key %r (expected 'provider/model')", key)
            continue
        provider, model = parts
        try:
            overrides[(provider, model)] = ModelPricing(**fields)
        except TypeError as exc:
            logger.warning("Skipping pricing entry %r: %s", key, exc)
    return overrides


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------

def _merged_table() -> dict[tuple[str, str], ModelPricing]:
    """Return the built-in table merged with any user overrides."""
    table = dict(PRICING_TABLE)
    table.update(_load_user_overrides())
    return table


def _resolve_pricing(provider: str | None, model: str | None) -> ModelPricing | None:
    """Look up pricing for a provider/model pair.

    Resolution order:
        1. Exact ``(provider, model)`` match.
        2. Prefix match — e.g. ``gpt-4o-2024-08-06`` matches the ``gpt-4o``
           entry because the table key is a prefix of the queried model name.
           When multiple prefixes match, the longest wins.
        3. Match on model alone across any provider if provider is None.

    Returns:
        The matching ``ModelPricing``, or ``None`` if nothing matches.
    """
    if model is None:
        return None

    table = _merged_table()

    # 1. Exact match with provider
    if provider is not None:
        exact = table.get((provider, model))
        if exact is not None:
            return exact

    # 2. Prefix match with provider
    best: ModelPricing | None = None
    best_len = 0
    for (tbl_provider, tbl_model), pricing in table.items():
        if provider is not None and tbl_provider != provider:
            continue
        if model.startswith(tbl_model) and len(tbl_model) > best_len:
            best = pricing
            best_len = len(tbl_model)

    if best is not None:
        return best

    # 3. Model prefix match ignoring provider (e.g. if provider is unset)
    for (_tbl_provider, tbl_model), pricing in table.items():
        if model.startswith(tbl_model) and len(tbl_model) > best_len:
            best = pricing
            best_len = len(tbl_model)

    return best


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_cost(span: Span) -> float | None:
    """Compute the USD cost for a single span accounting for cache hits and writes.

    For ephemeral prompt caching:
    - ``input_tokens`` represents total prompt tokens.
    - If ``cache_read_tokens > 0``, the uncached input tokens are
      ``max(0, input_tokens - cache_read_tokens)`` and are billed at standard rate.
    - ``cache_read_tokens`` are billed at the discounted ``cache_read_per_mtok`` rate.
    - ``cache_write_tokens`` are billed at ``cache_write_per_mtok`` rate.
    - ``output_tokens`` are billed at ``output_per_mtok`` rate.

    Args:
        span: A normalized span. Only ``SpanKind.LLM`` spans with a model
            name can be priced.

    Returns:
        Cost in USD, or ``None`` if the span is not an LLM call or no
        pricing data is available.
    """
    if span.kind != SpanKind.LLM or span.model is None:
        return None

    pricing = _resolve_pricing(span.provider, span.model)
    if pricing is None:
        return None

    # Calculate uncached vs cached input tokens
    uncached_input_tokens = max(0, span.input_tokens - span.cache_read_tokens)

    cost = (
        uncached_input_tokens * pricing.input_per_mtok
        + span.cache_read_tokens * pricing.cache_read_per_mtok
        + span.cache_write_tokens * pricing.cache_write_per_mtok
        + span.output_tokens * pricing.output_per_mtok
    ) / 1_000_000

    return cost


def enrich_spans(spans: list[Span]) -> list[Span]:
    """Return a new list of spans with ``cost`` filled in where possible."""
    enriched: list[Span] = []
    for span in spans:
        cost = compute_cost(span)
        if cost is not None:
            enriched.append(span.with_cost(cost))
        else:
            enriched.append(span)
    return enriched
