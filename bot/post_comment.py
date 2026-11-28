# Post the bot's comment on a PR, or update the one it posted before (C8).
#
# Usage:
#     python bot/post_comment.py --body-file comment.md   # a review, dry run, dummy or usage message
#     python bot/post_comment.py --failed                 # the review failed, see RUN_URL
#
# --repo and --pr default to the GITHUB_REPOSITORY and PR_NUMBER environment
# variables, as in review.py. Needs the `gh` CLI (GH_TOKEN in the workflow).
#
# The bot keeps two comments per PR, each the newest comment by BOT_LOGIN
# that contains its marker. Both must match: the workflow's token may be able
# to edit other people's comments, and anyone can paste a marker into theirs.
# - The review comment (MARKER) holds the last full review, for the contributor.
# - The preview comment (PREVIEW_MARKER) holds dry runs, dummy reports and the
#   usage message, for the maintainer. review.py puts PREVIEW_MARKER in those
#   bodies, so a preview never replaces the contributor's to-do list.
#
# - A new body replaces the whole comment, so a second /review edits the first
#   comment instead of adding another one. GitHub keeps the old text in the
#   comment's edit history.
# - --failed keeps what the comment said and puts a short failure note on top,
#   so one failed run doesn't hide the last review's to-do list. Further
#   failures only replace the note; the next successful run removes it.
#
# Editing a comment sends no notification, and the comment stays where it was
# first posted. The report names the reviewed commit, so readers can tell
# which push it is about.


import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from github_context import GitHubError, _gh_list

MARKER = "<!-- pr-bot-report -->"
PREVIEW_MARKER = "<!-- pr-bot-preview -->"
BOT_LOGIN = os.environ.get("BOT_LOGIN", "github-actions[bot]")  # who posts with the workflow's GITHUB_TOKEN

FAILED_START = "<!-- pr-bot-failed -->"
FAILED_END = "<!-- /pr-bot-failed -->"
FAILED_NOTE = "> ⚠️ **The latest review failed.** See the [run log]({run_url}).{kept}"
KEPT = " The bot's previous comment is kept below."
FAILED_BLOCK = re.compile(re.escape(FAILED_START) + r".*?" + re.escape(FAILED_END) + r"\n*", re.DOTALL)


def parse_args():
    parser = argparse.ArgumentParser(description="Post or update the bot's comment on a PR.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"), help="OWNER/REPO")
    parser.add_argument("--pr", type=int, default=os.environ.get("PR_NUMBER"), help="PR number")
    parser.add_argument("--run-url", default=os.environ.get("RUN_URL", "#"), help="link to the workflow run, for --failed")
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument("--body-file", type=Path, help="post this file as the comment")
    what.add_argument("--failed", action="store_true", help="note that the review failed, keeping the previous comment")
    args = parser.parse_args()
    if not args.repo or not args.pr:
        parser.error("--repo and --pr are required (or set GITHUB_REPOSITORY and PR_NUMBER)")
    return args


def marker_of(body):
    """The marker of the comment this body belongs in: previews carry
    PREVIEW_MARKER, everything else is a review."""
    return PREVIEW_MARKER if PREVIEW_MARKER in body else MARKER


def find_comment(repo, pr_number, marker=MARKER):
    """Return the newest comment the bot posted on this PR with this marker, or None."""
    comments = _gh_list(f"repos/{repo}/issues/{pr_number}/comments")
    ours = [c for c in comments if (c.get("user") or {}).get("login") == BOT_LOGIN and marker_of(c.get("body") or "") == marker and marker in c["body"]]
    return ours[-1] if ours else None  # the API lists comments oldest first


def content(body):
    """A comment body without markers and without a failure note."""
    body = FAILED_BLOCK.sub("", body.replace(PREVIEW_MARKER, "").replace(MARKER, ""))
    return body.strip("\n") + "\n" if body.strip() else ""


def compose(text, marker=MARKER, run_url=None):
    """The full comment: the marker, a failure note if run_url is given, then text."""
    parts = [marker]
    if run_url is not None:
        note = FAILED_NOTE.format(run_url=run_url, kept=KEPT if text else "")
        parts.append(f"{FAILED_START}\n{note}\n{FAILED_END}\n")
    parts.append(text)
    return "\n".join(parts).rstrip("\n") + "\n"


def _gh_send(method, path, body):
    """Create or edit a comment with `gh api`. The body goes in as JSON on
    stdin, so no part of it is ever read by a shell."""
    proc = subprocess.run(
        ["gh", "api", "-X", method, path, "--input", "-"],
        input=json.dumps({"body": body}).encode("utf-8"),
        capture_output=True,
    )
    if proc.returncode != 0:
        raise GitHubError(f"gh api -X {method} {path} failed: {proc.stderr.decode('utf-8', errors='replace').strip()}")
    return json.loads(proc.stdout or b"{}")


def post(repo, pr_number, text=None, run_url=None):
    """Update the bot's comment, or post one if it has none yet. With text,
    the review or preview comment (see marker_of) becomes text. Without it (a
    failed run), the review comment keeps its text and a failure note linking
    run_url goes on top."""
    marker = MARKER if text is None else marker_of(text)
    existing = find_comment(repo, pr_number, marker)
    if text is None:
        text = content(existing["body"]) if existing else ""
        body = compose(text, run_url=run_url)
    else:
        body = compose(content(text), marker)

    if existing:
        result = _gh_send("PATCH", f"repos/{repo}/issues/comments/{existing['id']}", body)
        action = "Updated"
    else:
        result = _gh_send("POST", f"repos/{repo}/issues/{pr_number}/comments", body)
        action = "Posted"
    print(f"{action} comment {result.get('html_url', '')}".rstrip(), file=sys.stderr)
    return result


def main():
    args = parse_args()
    text = None if args.failed else args.body_file.read_text(encoding="utf-8")
    try:
        post(args.repo, args.pr, text=text, run_url=args.run_url)
    except GitHubError as e:
        sys.exit(f"Posting the comment failed: {e}")


if __name__ == "__main__":
    main()
