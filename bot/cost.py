# Turn the token usage of a Claude answer into the numbers report.json keeps:
# input and output tokens, cache tokens, and the price in USD (issue #12).
#
# Prices are list prices per million tokens, copied by hand from
# https://platform.claude.com/docs/en/about-claude/pricing on PRICES_CHECKED.
# Update both when the prices change or claude_review.py moves to a model that
# isn't listed. An unlisted model still gets its tokens recorded; only its USD
# is left out (null), so a missing price never stops a review.
#
# With server-side fallbacks, one call can run more than one model: top-level
# usage covers only the attempt that answered, and usage.iterations lists every
# attempt with its own model. We add up all attempts at their own model's
# prices. A refused attempt that produced no output is billed only for some
# refusal categories, which the usage doesn't say, so the USD can be a little
# high in that rare case, never low.
#
# This module doesn't import anthropic, so it works on any object shaped like
# the SDK's message.usage, which keeps the tests free of API calls.


PRICES_CHECKED = "2026-11-28"

# $ per million tokens: base input, 5-minute and 1-hour cache writes, cache
# reads, output. Thinking tokens are part of output_tokens and cost the same.
PRICES = {
    "claude-opus-5-5": {"input": 4.00, "cache_write_5m": 5.00, "cache_write_1h": 8.00, "cache_read": 0.20, "output": 20.00},
    # Fallback models the API may pick with fallbacks="default".
    "claude-opus-5": {"input": 5.00, "cache_write_5m": 6.25, "cache_write_1h": 10.00, "cache_read": 0.50, "output": 25.00},
    "claude-opus-4-8": {"input": 5.00, "cache_write_5m": 6.25, "cache_write_1h": 10.00, "cache_read": 0.50, "output": 25.00},
}

TOKEN_FIELDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def _count(obj, field):
    """A token count from the SDK, where a missing field or None means 0."""
    return getattr(obj, field, None) or 0


def attempt_usd(model, tokens, cache_write_1h=0):
    """Price one attempt, or return None if the model has no listed price.
    `cache_write_1h` is the part of cache_creation_input_tokens written with
    the 1-hour TTL; the rest counts as 5-minute writes."""
    price = PRICES.get(model)
    if price is None:
        return None
    cache_write_5m = tokens["cache_creation_input_tokens"] - cache_write_1h
    dollars = (
        tokens["input_tokens"] * price["input"]
        + cache_write_5m * price["cache_write_5m"]
        + cache_write_1h * price["cache_write_1h"]
        + tokens["cache_read_input_tokens"] * price["cache_read"]
        + tokens["output_tokens"] * price["output"]
    )
    return dollars / 1_000_000


def _attempts(message):
    """One (model, usage) pair per attempt that ran in this call."""
    usage = message.usage
    iterations = getattr(usage, "iterations", None)
    if not iterations:
        return [(message.model, usage)]
    # A "message" entry may leave out its model when it is the one requested.
    return [(getattr(entry, "model", None) or message.model, entry) for entry in iterations]


def usage_report(message):
    """Return the usage dict that goes into report.json under "usage"."""
    attempts, dollars = [], []
    for model, usage in _attempts(message):
        tokens = {field: _count(usage, field) for field in TOKEN_FIELDS}
        cache_write_1h = _count(getattr(usage, "cache_creation", None), "ephemeral_1h_input_tokens")
        usd = attempt_usd(model, tokens, cache_write_1h)
        dollars.append(usd)
        attempts.append({"model": model, **tokens, "usd": None if usd is None else round(usd, 6)})

    report = {field: sum(a[field] for a in attempts) for field in TOKEN_FIELDS}
    # Part of output_tokens, kept to see what the effort setting costs. Only
    # the answering attempt reports it.
    thinking = _count(getattr(message.usage, "output_tokens_details", None), "thinking_tokens")
    if thinking:
        report["thinking_tokens"] = thinking
    report["usd"] = None if None in dollars else round(sum(dollars), 6)
    report["prices_checked"] = PRICES_CHECKED
    if len(attempts) > 1:
        report["attempts"] = attempts
    return report


def summary(report):
    """One line for the workflow log."""
    usd = "unknown (model not in cost.PRICES)" if report["usd"] is None else f"${report['usd']:.4f}"
    return f"input_tokens={report['input_tokens']} output_tokens={report['output_tokens']} " f"cache_read={report['cache_read_input_tokens']} usd={usd}"
