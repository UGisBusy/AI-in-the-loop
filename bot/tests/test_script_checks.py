# Written by AI (Claude Opus 5.5 in Claude Code). The fixtures are real PR
# descriptions from linkedin-mcp-server. Run with:
#     python -m unittest discover -s bot

import unittest
from pathlib import Path

import script_checks
from report import load_parts, render

FIXTURES = Path(__file__).with_name("fixtures")
PARTS = load_parts()
SCRIPTED = ["summary_filled", "verification_filled", "prompt_filled"]


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def statuses(body):
    results, _ = script_checks.run(PARTS, body)
    return {i: results[i]["status"] for i in SCRIPTED}


class ScriptChecksTest(unittest.TestCase):
    # AI-written: PR 1480 left the template untouched; its '-' and '>'
    # placeholders and HTML hints are not content.
    def test_untouched_template_fails_every_section(self):
        self.assertEqual(statuses(fixture("linkedin-mcp-server-pr1480.md")), dict.fromkeys(SCRIPTED, "fail"))

    # AI-written: a fully filled description passes all three.
    def test_filled_description_passes(self):
        self.assertEqual(statuses(fixture("linkedin-mcp-server-pr1530.md")), dict.fromkeys(SCRIPTED, "pass"))

    # AI-written: PR 1530 with its quote emptied back to the template's '>'.
    def test_bare_quote_fails_prompt(self):
        body = fixture("linkedin-mcp-server-pr1530.md")
        quote = next(line for line in body.splitlines() if line.startswith("> "))
        self.assertEqual(statuses(body.replace(quote, ">")), {"summary_filled": "pass", "verification_filled": "pass", "prompt_filled": "fail"})

    # AI-written: PR 1521 with its quote emptied; the Macroscope summary that a
    # bot quoted below it is not the contributor's prompt.
    def test_bot_summary_quote_is_not_a_prompt(self):
        body = fixture("linkedin-mcp-server-pr1521.md")
        quote = next(line for line in body.splitlines() if line.startswith("> "))
        self.assertEqual(statuses(body)["prompt_filled"], "pass")
        self.assertEqual(statuses(body.replace(quote, ">"))["prompt_filled"], "fail")

    # AI-written: PR 1561 has no Synthetic prompt section at all.
    def test_missing_section_fails_prompt(self):
        self.assertEqual(statuses(fixture("linkedin-mcp-server-pr1561.md"))["prompt_filled"], "fail")

    # AI-written: PR 1415 has no Verification section; a Markdown table and
    # images in the Summary still count as content.
    def test_missing_verification_fails(self):
        self.assertEqual(statuses(fixture("linkedin-mcp-server-pr1415.md")), {"summary_filled": "pass", "verification_filled": "fail", "prompt_filled": "pass"})

    # AI-written: a Solution section counts as the Summary.
    def test_solution_counts_as_summary(self):
        results, _ = script_checks.run(PARTS, "## Solution\n\nAdds a flag.\n")
        self.assertEqual(results["summary_filled"]["status"], "pass")

    # AI-written: the same description gives the same results on every run.
    def test_repeat_runs_agree(self):
        body = fixture("linkedin-mcp-server-pr1561.md")
        self.assertEqual(script_checks.run(PARTS, body)[0], script_checks.run(PARTS, body)[0])


class SplitAndMergeTest(unittest.TestCase):
    # AI-written: Claude gets every point except the three checked here, and the
    # merged report has one result per point and renders.
    def test_claude_gets_the_rest_and_report_is_complete(self):
        body = fixture("linkedin-mcp-server-pr1561.md")
        script_results, llm_parts = script_checks.run(PARTS, body)
        llm_ids = [p["id"] for part in llm_parts for p in part["points"]]
        all_ids = [p["id"] for part in PARTS for p in part["points"]]
        self.assertEqual(llm_ids, [i for i in all_ids if i not in SCRIPTED])

        llm_results = [{"id": i, "status": "pass", "explanation": "ok", "requested_change": ""} for i in llm_ids]
        merged = script_checks.merge(PARTS, script_results, llm_results)
        self.assertEqual([r["id"] for r in merged], all_ids)
        comment = render({"head_sha": "0" * 40, "requested_by": "test", "criteria": merged})
        self.assertIn("Changes requested", comment)
        self.assertIn("A quoted prompt is filled in:", comment)


if __name__ == "__main__":
    unittest.main()
