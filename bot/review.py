"""Review a pull request and print the PR comment on stdout.

Usage:
    python bot/review.py --repo OWNER/REPO --pr 123 [--report-out report.json]
    python bot/review.py ... --dry-run   # print the prompt, don't call Claude
    python bot/review.py ... --dummy     # use sample_report.json, no API calls

In the workflow, --repo and --pr come from the GITHUB_REPOSITORY and
PR_NUMBER environment variables, and REQUESTED_BY names who asked.

Needs the `gh` CLI with access to the repository (GH_TOKEN in the workflow)
and ANTHROPIC_API_KEY for the Claude call.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from report import load_parts, render

SAMPLE_FILE = Path(__file__).with_name("sample_report.json")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"), help="OWNER/REPO")
    parser.add_argument("--pr", type=int, default=os.environ.get("PR_NUMBER"), help="PR number")
    parser.add_argument("--requested-by", default=os.environ.get("REQUESTED_BY", "unknown"))
    parser.add_argument("--report-out", type=Path, help="also write the report as JSON to this file")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print the prompt instead of calling Claude")
    mode.add_argument("--dummy", action="store_true", help="render sample_report.json, no API calls")
    args = parser.parse_args()
    if not args.dummy and (not args.repo or not args.pr):
        parser.error("--repo and --pr are required (or set GITHUB_REPOSITORY and PR_NUMBER)")
    return args


def dummy_results(parts):
    """Sample results for every point. Points missing from the sample pass."""
    sample = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))
    samples = {c["id"]: c for c in sample["criteria"]}
    placeholder = {"status": "pass", "explanation": "Not checked yet (dummy).", "requested_change": ""}
    return [
        samples.get(point["id"], {"id": point["id"], **placeholder})
        for part in parts
        for point in part["points"]
    ]


def main():
    args = parse_args()
    # The comment contains emoji; make sure stdout can encode them on any OS.
    sys.stdout.reconfigure(encoding="utf-8")
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

    if args.dry_run:
        print("=== SYSTEM ===")
        print(claude_review.build_system(parts, context))
        print("=== USER ===")
        print(claude_review.build_user(context))
        return

    try:
        results, model = claude_review.review(parts, context)
    except claude_review.ReviewError as e:
        sys.exit(f"Review failed: {e}")

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
