# Tests for --save-context and --context-file (C4).
#
# Run from the repository root:
#     python -m unittest discover bot
#
# GitHub is faked: _gh answers from FAKE_API, so no network or gh CLI is needed.


import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))

import github_context  # noqa: E402
import review  # noqa: E402

REPO, PR, BASE, HEAD = "octo/demo", 7, "b" * 40, "h" * 40

FAKE_API = {
    f"repos/{REPO}/pulls/{PR}": {
        "title": "Add greeting",
        "body": "Adds a greeting.\n\nCloses #3",
        "user": {"login": "contributor"},
        "base": {"ref": "main", "sha": BASE},
        "head": {"sha": HEAD, "repo": {"full_name": REPO}},
    },
    f"repos/{REPO}/contents/README.md?ref={BASE}": b"# Demo\n",
    f"repos/{REPO}/git/trees/{BASE}?recursive=1": {"tree": [{"path": "README.md", "type": "blob"}, {"path": "hello.py", "type": "blob"}]},
    f"repos/{REPO}/pulls/{PR}/commits?per_page=100&page=1": [{"commit": {"message": "add greeting\n\nlonger text"}}],
    f"repos/{REPO}/issues/3": {"title": "Say hello", "body": "We should greet users."},
    f"repos/{REPO}/pulls/{PR}/files?per_page=100&page=1": [
        {"filename": "hello.py", "status": "modified", "additions": 1, "deletions": 0, "patch": "@@ -1 +1,2 @@\n+print('hi')"},
    ],
    f"repos/{REPO}/contents/hello.py?ref={HEAD}": b"print('hi')\n",
}


def fake_gh(path, raw=False):
    body = FAKE_API.get(path)
    if body is None or isinstance(body, bytes):
        return body
    return json.dumps(body)


def no_github(*args, **kwargs):
    raise AssertionError("GitHub was called, but --context-file should need no GitHub calls")


def run_review(argv):
    """Run review.py's main() with these arguments and return what it prints."""
    out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    with mock.patch.object(sys, "argv", ["review.py", *argv]), mock.patch.object(sys, "stdout", out):
        review.main()
        out.flush()
        return out.buffer.getvalue().decode("utf-8")


class ContextFileTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.ctx = self.tmp / "ctx.json"

    def save(self):
        with mock.patch.object(github_context, "_gh", fake_gh):
            return run_review(["--repo", REPO, "--pr", str(PR), "--dry-run", "--save-context", str(self.ctx)])

    def test_saved_context_gives_same_prompt_without_github(self):
        # AI-written (Claude Opus 5.5).
        live_prompt = self.save()
        self.assertIn("Add greeting", live_prompt)
        with mock.patch.object(github_context, "_gh", no_github), mock.patch("subprocess.run", no_github):
            replayed_prompt = run_review(["--context-file", str(self.ctx), "--dry-run"])
        self.assertEqual(live_prompt, replayed_prompt)

    def test_context_file_overrides_repo_and_pr(self):
        # AI-written (Claude Opus 5.5).
        self.save()
        with mock.patch.object(github_context, "_gh", no_github):
            prompt = run_review(["--repo", "other/repo", "--pr", "99", "--context-file", str(self.ctx), "--dry-run"])
        self.assertIn(REPO, prompt)
        self.assertNotIn("other/repo", prompt)

    def test_saved_file_records_format(self):
        # AI-written (Claude Opus 5.5).
        self.save()
        data = json.loads(self.ctx.read_text(encoding="utf-8"))
        self.assertEqual(data["format"], review.CONTEXT_FORMAT)
        self.assertEqual(data["context"]["pr_number"], PR)

    def test_bad_context_files_exit_with_a_message(self):
        # AI-written (Claude Opus 5.5).
        cases = {
            "missing.json": None,
            "not_json.json": "{oops",
            "report.json": json.dumps({"repo": REPO, "criteria": []}),
            "partial.json": json.dumps({"format": review.CONTEXT_FORMAT, "context": {"repo": REPO}}),
        }
        for name, text in cases.items():
            path = self.tmp / name
            if text is not None:
                path.write_text(text, encoding="utf-8")
            with self.subTest(name), self.assertRaises(SystemExit) as caught:
                review.load_context(path)
            self.assertIsInstance(caught.exception.code, str)

    def test_dummy_rejects_context_options(self):
        # AI-written (Claude Opus 5.5).
        with mock.patch.object(sys, "stderr", io.StringIO()), self.assertRaises(SystemExit):
            run_review(["--dummy", "--context-file", str(self.ctx)])


if __name__ == "__main__":
    unittest.main()
