# Review a pull request and print the PR comment on stdout.
#
# Usage:
#     python bot/review.py --repo OWNER/REPO --pr 123 [--report-out report.json]
#     python bot/review.py ... --dry-run   # print the prompt, don't call Claude
#     python bot/review.py ... --dummy     # use sample_report.json, no API calls
#
# In the workflow, --repo and --pr come from the GITHUB_REPOSITORY and
# PR_NUMBER environment variables, and REQUESTED_BY names who asked.
#
# The PR comment that triggered the run comes in REVIEW_COMMAND. Its first line
# picks the mode: "/review", "/review --dry-run" or "/review --dummy". With
# --prompt-out, a dry run writes the prompt to that file and prints a short
# summary instead, because the prompt is too long for a PR comment.
#
# Needs the `gh` CLI with access to the repository (GH_TOKEN in the workflow)
# and ANTHROPIC_API_KEY for the Claude call.


import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import script_checks
from report import load_parts, render

SAMPLE_FILE = Path(__file__).with_name("sample_report.json")

# Options allowed after /review in a PR comment.
COMMENT_OPTIONS = {"--dry-run": "dry_run", "--dummy": "dummy"}
USAGE_COMMENT = "🤖 {problem}. Use one of:\n\n" "- `/review`: full review with Claude\n" "- `/review --dry-run`: collect the context and attach the prompt, without calling Claude\n" "- `/review --dummy`: post a sample report, no API calls"

DRY_RUN_TEMPLATE = """\
## 🤖 PR review: dry run

No Claude call was made. The full prompt is attached to the [workflow run]({run_url}) as `prompt.txt`.

**Prompt size:** {chars:,} characters, about {tokens:,} tokens

| Changed file | Sent as |
|---|---|
{file_rows}

**Left out or cut:**
{omitted}
"""


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"), help="OWNER/REPO")
    parser.add_argument("--pr", type=int, default=os.environ.get("PR_NUMBER"), help="PR number")
    parser.add_argument("--requested-by", default=os.environ.get("REQUESTED_BY", "unknown"))
    parser.add_argument("--command", default=os.environ.get("REVIEW_COMMAND"), help="the /review comment text")
    parser.add_argument("--report-out", type=Path, help="also write the report as JSON to this file")
    parser.add_argument("--prompt-out", type=Path, help="dry run: write the prompt here, print a summary")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print the prompt instead of calling Claude")
    mode.add_argument("--dummy", action="store_true", help="render sample_report.json, no API calls")
    args = parser.parse_args()
    if not args.dummy and (not args.repo or not args.pr):
        parser.error("--repo and --pr are required (or set GITHUB_REPOSITORY and PR_NUMBER)")
    return args


def apply_command(args):
    """Set the mode from the comment's first line. Return a usage message for
    unknown options, or None if the command is fine."""
    if not args.command:
        return None
    words = args.command.strip().splitlines()[0].split()
    options = words[1:] if words and words[0] == "/review" else words
    unknown = [o for o in options if o not in COMMENT_OPTIONS]
    if unknown:
        s = "s" if len(unknown) > 1 else ""
        return USAGE_COMMENT.format(problem=f"Unknown option{s}: " + ", ".join(f"`{o}`" for o in unknown))
    if len(options) > 1:
        return USAGE_COMMENT.format(problem="Use only one option at a time")
    for option in options:
        setattr(args, COMMENT_OPTIONS[option], True)
    return None


def dry_run_summary(context, prompt_chars):
    rows = []
    for f in context["files"]:
        if f["content"] is not None:
            sent = "full file and diff"
        elif f["patch"] is not None:
            sent = "diff only"
        else:
            sent = "not included"
        rows.append(f"| `{f['path']}` | {sent} |")
    return DRY_RUN_TEMPLATE.format(
        run_url=os.environ.get("RUN_URL", "#"),
        chars=prompt_chars,
        tokens=prompt_chars // 4,
        file_rows="\n".join(rows) or "| (none) | |",
        omitted="\n".join(f"- {o}" for o in context["omitted"]) or "- nothing",
    )


def dummy_results(parts):
    """Sample results for every point. Points missing from the sample pass."""
    sample = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))
    samples = {c["id"]: c for c in sample["criteria"]}
    placeholder = {"status": "pass", "explanation": "Not checked yet (dummy).", "requested_change": ""}
    return [samples.get(point["id"], {"id": point["id"], **placeholder}) for part in parts for point in part["points"]]


def main():
    args = parse_args()
    # The comment contains emoji; make sure stdout can encode them on any OS.
    sys.stdout.reconfigure(encoding="utf-8")

    usage = apply_command(args)
    if usage:
        print(usage)
        return

    parts = load_parts()

    if args.dummy:
        report = {
            "repo": args.repo,
            "pr": args.pr or 0,
            "head_sha": "0" * 40,
            "requested_by": args.requested_by,
            "model": "dummy",
            "criteria": dummy_results(parts),
        }
        print("> ⚠️ **Dummy data:** no real review was run.\n")
        print(render(report))
        return

    # Imported here so --dummy works without the anthropic package installed.
    import claude_review
    import github_context

    try:
        if not args.dry_run:
            claude_review.check_credentials()
        context = github_context.collect(args.repo, args.pr)
    except (claude_review.ReviewError, github_context.GitHubError) as e:
        sys.exit(f"Review failed: {e}")

    script_results, llm_parts = script_checks.run(parts, context["body"])

    if args.dry_run:
        prompt = "=== SYSTEM ===\n" + claude_review.build_system(llm_parts, context) + "\n=== USER ===\n" + claude_review.build_user(context) + "\n"
        if args.prompt_out:
            args.prompt_out.write_text(prompt, encoding="utf-8")
            print(dry_run_summary(context, len(prompt)))
        else:
            print(prompt, end="")
        return

    try:
        llm_results, model = claude_review.review(llm_parts, context)
    except claude_review.ReviewError as e:
        sys.exit(f"Review failed: {e}")
    results = script_checks.merge(parts, script_results, llm_results)

    report = {
        "repo": args.repo,
        "pr": args.pr,
        "pr_author": context["author"],
        "head_sha": context["head_sha"],
        "requested_by": args.requested_by,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": model,
        "context_omitted": context["omitted"],
        "criteria": results,
    }
    if args.report_out:
        args.report_out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(render(report))


if __name__ == "__main__":
    main()
