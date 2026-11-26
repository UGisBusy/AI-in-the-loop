# Collect what the reviewer needs to know about a PR and its repository.
#
# Everything is read through the GitHub API with the `gh` CLI, so the PR's code
# is never checked out or run. That matters because the workflow has secrets.
#
# Two kinds of context:
# - Repository rules (PR template, contributing guide, agent guide, README) and
#   the file tree, read from the PR's *base* commit. A PR that edits these files
#   can't change the rules it is judged by.
# - The PR itself: title, description, commits, linked issues, the diff, and
#   the full new version of each changed file, read from the PR's head commit.
#   Files over MAX_FILE_CHARS, and files matching DIFF_ONLY_PATTERNS, are sent
#   as their diff only.
#
# Large items are cut to fit a size budget. Whatever is cut is listed in
# `omitted`, and the prompt tells the model about it.


import json
import re
import subprocess
import sys
from fnmatch import fnmatch
from urllib.parse import quote

# Size limits, in characters (about 4 characters per token).
MAX_TOTAL_CHARS = 400_000  # whole context, roughly 100k tokens
MAX_DOC_CHARS = 40_000  # one repository guide file
# A changed file larger than this is sent as its diff only. 50k covers about
# 83% of the source files changed in linkedin-mcp-server's recent PRs.
MAX_FILE_CHARS = 50_000
MAX_ISSUE_CHARS = 10_000  # one linked issue's description
MAX_TREE_PATHS = 3_000  # paths listed from the file tree
MAX_LINKED_ISSUES = 3
MAX_COMMITS = 100

# Changed files whose full content tells the reviewer nothing: lockfiles,
# generated files and test fixtures. Only their diff is sent.
DIFF_ONLY_PATTERNS = [
    "*.lock",
    "*package-lock.json",
    "*pnpm-lock.yaml",
    "tests/fixtures/*",
    "docs/linkedin-architecture.md",  # generated in linkedin-mcp-server
]

# Repository guides, by kind. For each kind, the first path that exists is used.
GUIDE_FILES = {
    "pr_template": [
        ".github/pull_request_template.md",
        ".github/PULL_REQUEST_TEMPLATE.md",
        "pull_request_template.md",
        "docs/pull_request_template.md",
    ],
    "contributing": [".github/CONTRIBUTING.md", "CONTRIBUTING.md", "docs/CONTRIBUTING.md"],
    "agents": ["AGENTS.md", "CLAUDE.md"],
    "readme": ["README.md"],
}


class GitHubError(RuntimeError):
    pass


def _gh(path, raw=False):
    """Call `gh api` and return the body, or None on 404.

    The body is text, except with raw=True, where it is the file's bytes: a raw
    file may be binary, so the caller decides whether to decode it.
    """
    cmd = ["gh", "api", path]
    if raw:
        cmd += ["-H", "Accept: application/vnd.github.raw"]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace")
        if "404" in stderr or "Not Found" in stderr:
            return None
        raise GitHubError(f"gh api {path} failed: {stderr.strip()}")
    return proc.stdout if raw else proc.stdout.decode("utf-8")


def _gh_json(path):
    body = _gh(path)
    return None if body is None else json.loads(body)


def _gh_list(path, limit=None):
    """Fetch every page of a list endpoint."""
    items, page = [], 1
    sep = "&" if "?" in path else "?"
    while True:
        batch = _gh_json(f"{path}{sep}per_page=100&page={page}") or []
        items.extend(batch)
        if len(batch) < 100 or (limit and len(items) >= limit):
            return items[:limit] if limit else items
        page += 1


def _file_at(repo, path, ref):
    """Return a file's text at `ref`, or None if it is missing or not UTF-8 text."""
    data = _gh(f"repos/{repo}/contents/{quote(path)}?ref={ref}", raw=True)
    if data is None or b"\x00" in data:
        return None  # missing, or binary (images, archives, ...)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None  # binary, or text in another encoding


def _cut(text, limit, label, omitted):
    if text is None or len(text) <= limit:
        return text
    omitted.append(f"{label}: cut to the first {limit:,} of {len(text):,} characters")
    return text[:limit]


def _linked_issue_numbers(repo, pr_number, text):
    owner_repo = re.escape(repo)
    numbers = re.findall(r"(?<![\w/])#(\d+)\b", text or "")
    numbers += re.findall(rf"github\.com/{owner_repo}/issues/(\d+)", text or "", re.IGNORECASE)
    seen = []
    for n in map(int, numbers):
        if n != pr_number and n not in seen:
            seen.append(n)
    return seen[:MAX_LINKED_ISSUES]


def collect(repo, pr_number):
    """Return a dict with everything the prompt needs."""
    omitted = []

    pr = _gh_json(f"repos/{repo}/pulls/{pr_number}")
    if pr is None:
        raise GitHubError(f"PR #{pr_number} not found in {repo}")

    base_sha = pr["base"]["sha"]
    head_sha = pr["head"]["sha"]
    # For a PR from a fork, the new file versions live in the fork. If the fork
    # was deleted, fall back to the base repository, which also has the commits.
    head_repo = (pr["head"].get("repo") or {}).get("full_name") or repo

    # Repository rules, from the base commit.
    guides = {}
    for kind, candidates in GUIDE_FILES.items():
        for path in candidates:
            text = _file_at(repo, path, base_sha)
            if text is not None:
                guides[kind] = {"path": path, "text": _cut(text, MAX_DOC_CHARS, path, omitted)}
                break

    tree = _gh_json(f"repos/{repo}/git/trees/{base_sha}?recursive=1") or {}
    paths = [item["path"] for item in tree.get("tree", []) if item["type"] == "blob"]
    if tree.get("truncated") or len(paths) > MAX_TREE_PATHS:
        omitted.append(f"file tree: listed {min(len(paths), MAX_TREE_PATHS):,} paths, the repository has more")
        paths = paths[:MAX_TREE_PATHS]

    # The PR itself.
    commits = _gh_list(f"repos/{repo}/pulls/{pr_number}/commits", limit=MAX_COMMITS)
    commit_messages = [c["commit"]["message"].splitlines()[0] for c in commits]

    issues = []
    for number in _linked_issue_numbers(repo, pr_number, pr.get("body")):
        issue = _gh_json(f"repos/{repo}/issues/{number}")
        if issue:
            issues.append(
                {
                    "number": number,
                    "title": issue["title"],
                    "body": _cut(issue.get("body") or "", MAX_ISSUE_CHARS, f"issue #{number}", omitted),
                }
            )

    files, patches = [], {}
    for f in _gh_list(f"repos/{repo}/pulls/{pr_number}/files"):
        # "patch" is missing for binary or very large diffs.
        patches[f["filename"]] = f.get("patch")
        files.append(
            {
                "path": f["filename"],
                "status": f["status"],
                "additions": f["additions"],
                "deletions": f["deletions"],
                "patch": None,
                "content": None,
            }
        )

    context = {
        "repo": repo,
        "pr_number": pr_number,
        "title": pr["title"],
        "body": pr.get("body") or "",
        "author": pr["user"]["login"],
        "base_ref": pr["base"]["ref"],
        "base_sha": base_sha,
        "head_sha": head_sha,
        "commit_messages": commit_messages,
        "linked_issues": issues,
        "guides": guides,
        "tree": paths,
        "files": files,
        "omitted": omitted,
    }

    # Spend what's left of the budget on diffs first, then on full file contents.
    used = _size(context)
    for f in files:
        patch = patches[f["path"]]
        if patch is None:
            omitted.append(f"{f['path']}: GitHub returned no diff (binary or too large)")
        elif used + len(patch) > MAX_TOTAL_CHARS:
            omitted.append(f"{f['path']}: diff left out, the context size budget ran out")
        else:
            f["patch"] = patch
            used += len(patch)

    for f in files:
        if f["status"] == "removed":
            continue
        if any(fnmatch(f["path"], pattern) for pattern in DIFF_ONLY_PATTERNS):
            continue  # lockfile, generated file or fixture: the diff is enough
        text = _file_at(head_repo, f["path"], head_sha)
        if text is None:
            continue  # missing or binary: its diff (if any) is all we send
        if len(text) > MAX_FILE_CHARS:
            omitted.append(f"{f['path']}: full file not sent ({len(text):,} characters, " f"over the {MAX_FILE_CHARS:,} limit), only its diff")
            continue
        if used + len(text) > MAX_TOTAL_CHARS:
            omitted.append(f"{f['path']}: full file left out, the context size budget ran out")
            continue
        f["content"] = text
        used += len(text)

    print(f"Context: {len(files)} changed files, ~{used:,} characters, {len(omitted)} items cut", file=sys.stderr)
    return context


def _size(context):
    return len(json.dumps(context, ensure_ascii=False))
