# Written by AI (Claude Opus 5.5 in Claude Code). Claude is faked: the usage
# objects are SimpleNamespaces shaped like the SDK's, and the end-to-end test
# swaps in a fake Anthropic client, so no test calls the API. Run with:
#     python -m unittest discover -s bot

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import claude_review
import cost
import review
import script_checks
from report import load_parts


def usage(input_tokens=0, output_tokens=0, cache_creation=None, cache_read=None, **extra):
    """An SDK-like usage object. Cache fields default to None, as the SDK sends
    them when caching isn't used."""
    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=cache_creation,
        cache_read_input_tokens=cache_read,
        **extra,
    )


def message(model="claude-opus-5-5", **usage_fields):
    return SimpleNamespace(model=model, usage=usage(**usage_fields))


class UsageReportTest(unittest.TestCase):
    # AI-written: a plain call is priced at Opus 5.5's list price, $4 in and
    # $20 out per million tokens, and keeps the thinking tokens apart.
    def test_plain_call(self):
        msg = message(input_tokens=10_000, output_tokens=2_000, output_tokens_details=SimpleNamespace(thinking_tokens=1_500))
        report = cost.usage_report(msg)
        self.assertEqual(report["input_tokens"], 10_000)
        self.assertEqual(report["output_tokens"], 2_000)
        self.assertEqual(report["cache_creation_input_tokens"], 0)
        self.assertEqual(report["cache_read_input_tokens"], 0)
        self.assertEqual(report["thinking_tokens"], 1_500)
        self.assertAlmostEqual(report["usd"], 0.08)
        self.assertEqual(report["prices_checked"], cost.PRICES_CHECKED)
        self.assertNotIn("attempts", report)

    # AI-written: cache reads cost $0.20 and 5-minute cache writes $5 per
    # million tokens on Opus 5.5.
    def test_cache_tokens(self):
        msg = message(input_tokens=1_000, cache_read=100_000, cache_creation=20_000)
        self.assertAlmostEqual(cost.usage_report(msg)["usd"], 0.124)

    # AI-written: cache writes with the 1-hour TTL cost $8 per million tokens.
    def test_one_hour_cache_writes(self):
        msg = message(cache_creation=20_000)
        msg.usage.cache_creation = SimpleNamespace(ephemeral_5m_input_tokens=0, ephemeral_1h_input_tokens=20_000)
        self.assertAlmostEqual(cost.usage_report(msg)["usd"], 0.16)

    # AI-written: when a fallback model answers, top-level usage covers only
    # that attempt, so every attempt in usage.iterations is added up at its own
    # model's price.
    def test_fallback_attempts_are_added_up(self):
        msg = message(model="claude-opus-4-8", input_tokens=5_000, output_tokens=1_000)
        msg.usage.iterations = [
            SimpleNamespace(type="message", model="claude-opus-5-5", input_tokens=5_000, output_tokens=0, cache_creation_input_tokens=0, cache_read_input_tokens=0),
            SimpleNamespace(type="fallback_message", model="claude-opus-4-8", input_tokens=5_000, output_tokens=1_000, cache_creation_input_tokens=0, cache_read_input_tokens=0),
        ]
        report = cost.usage_report(msg)
        self.assertEqual(report["input_tokens"], 10_000)
        self.assertEqual(report["output_tokens"], 1_000)
        self.assertAlmostEqual(report["usd"], 0.02 + 0.05)
        self.assertEqual([a["model"] for a in report["attempts"]], ["claude-opus-5-5", "claude-opus-4-8"])

    # AI-written: a "message" iteration without a model is the model the
    # message names.
    def test_iteration_without_model(self):
        msg = message(input_tokens=1_000)
        msg.usage.iterations = [SimpleNamespace(type="message", model=None, input_tokens=1_000, output_tokens=0, cache_creation_input_tokens=0, cache_read_input_tokens=0)]
        self.assertAlmostEqual(cost.usage_report(msg)["usd"], 0.004)

    # AI-written: a model without a listed price keeps its tokens, and only
    # the USD is null, so a new model can't break a review.
    def test_unknown_model_has_no_usd(self):
        report = cost.usage_report(message(model="claude-new-model", input_tokens=1_000, output_tokens=10))
        self.assertEqual(report["input_tokens"], 1_000)
        self.assertIsNone(report["usd"])
        self.assertIn("unknown", cost.summary(report))


# A PR context as --save-context writes it, small enough to read at a glance.
CONTEXT = {
    "repo": "octo/demo", "pr_number": 7, "title": "Add greeting", "body": "## Summary\nAdds a greeting.",
    "author": "contributor", "base_ref": "main", "base_sha": "b" * 40, "head_sha": "h" * 40,
    "commit_messages": ["add greeting"], "linked_issues": [], "guides": {}, "tree": ["hello.py"],
    "files": [], "omitted": [],
}  # fmt: skip


def fake_claude(answer):
    """A stand-in for anthropic.Anthropic whose streamed call returns `answer`."""

    def stream(**kwargs):
        return contextlib.nullcontext(SimpleNamespace(get_final_message=lambda: answer))

    return lambda: SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))


class ReportUsageTest(unittest.TestCase):
    # AI-written: a full review writes the call's tokens and USD into
    # report.json, which is what C7 is done for.
    def test_report_json_holds_tokens_and_usd(self):
        _, llm_parts = script_checks.run(load_parts(), CONTEXT["body"])
        results = [{"id": p["id"], "status": "pass", "explanation": "ok", "requested_change": ""} for part in llm_parts for p in part["points"]]
        answer = SimpleNamespace(
            model="claude-opus-5-5",
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=json.dumps({"results": results}))],
            usage=usage(input_tokens=30_000, output_tokens=4_000),
        )

        with tempfile.TemporaryDirectory() as tmp:
            ctx, out = Path(tmp) / "ctx.json", Path(tmp) / "report.json"
            ctx.write_text(json.dumps({"format": review.CONTEXT_FORMAT, "context": CONTEXT}), encoding="utf-8")
            argv = ["review.py", "--context-file", str(ctx), "--report-out", str(out)]
            stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(sys, "stdout", stdout),
                mock.patch.object(sys, "stderr", io.StringIO()),
                mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-not-real"}),
                mock.patch.object(claude_review.anthropic, "Anthropic", fake_claude(answer)),
            ):
                review.main()
            report = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(report["usage"]["input_tokens"], 30_000)
        self.assertEqual(report["usage"]["output_tokens"], 4_000)
        self.assertAlmostEqual(report["usage"]["usd"], 0.2)


if __name__ == "__main__":
    unittest.main()
