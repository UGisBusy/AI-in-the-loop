# Written by AI (Claude Opus 5.5 in Claude Code). GitHub is faked: FakeGitHub
# keeps the PR's comments in memory and applies the bot's POST and PATCH calls
# to them, so no network or gh CLI is needed. Run with:
#     python -m unittest discover -s bot

import io
import json
import sys
import unittest
from unittest import mock

import github_context
import post_comment
from post_comment import BOT_LOGIN, MARKER, post

REPO, PR = "octo/demo", 7
REPORT = MARKER + "\n## 🤖 PR review: 60/100 · Changes requested\n\n- [ ] **Issue link:** No issue is linked.\n"
NEW_REPORT = MARKER + "\n## 🤖 PR review: 100/100 · Ready for human review\n"
RUN_1, RUN_2 = "https://example.test/runs/1", "https://example.test/runs/2"


class FakeGitHub:
    """The comments on one PR, oldest first, served 100 per page like the API."""

    def __init__(self, *comments):
        self.comments = [{"id": i + 1, "user": {"login": login}, "body": body} for i, (login, body) in enumerate(comments)]
        self.sent = []

    def gh(self, path, raw=False):
        prefix = f"repos/{REPO}/issues/{PR}/comments?per_page=100&page="
        assert path.startswith(prefix), path
        page = int(path[len(prefix) :])
        return json.dumps(self.comments[(page - 1) * 100 : page * 100])

    def send(self, method, path, body):
        self.sent.append((method, path))
        if method == "POST":
            assert path == f"repos/{REPO}/issues/{PR}/comments", path
            comment = {"id": len(self.comments) + 1, "user": {"login": BOT_LOGIN}, "body": body}
            self.comments.append(comment)
            return {**comment, "html_url": f"https://github.test/c/{comment['id']}"}
        comment_id = int(path.rsplit("/", 1)[1])
        comment = next(c for c in self.comments if c["id"] == comment_id)
        comment["body"] = body
        return comment

    def body(self, comment_id):
        return next(c for c in self.comments if c["id"] == comment_id)["body"]


class PostCommentTest(unittest.TestCase):
    def run_post(self, fake, text=None, run_url=None):
        with (
            mock.patch.object(github_context, "_gh", fake.gh),
            mock.patch.object(post_comment, "_gh_send", fake.send),
            mock.patch.object(sys, "stderr", io.StringIO()),
        ):
            return post(REPO, PR, text=text, run_url=run_url)

    # AI-written: the first review on a PR posts a new comment.
    def test_first_review_posts(self):
        fake = FakeGitHub(("alice", "/review"))
        self.run_post(fake, REPORT)
        self.assertEqual(fake.sent, [("POST", f"repos/{REPO}/issues/{PR}/comments")])
        self.assertEqual(fake.body(2), REPORT)

    # AI-written: a second review edits the first comment instead of adding
    # one, which is what C8 is done for.
    def test_second_review_edits_first_comment(self):
        fake = FakeGitHub(("alice", "/review"), (BOT_LOGIN, REPORT), ("alice", "/review"))
        self.run_post(fake, NEW_REPORT)
        self.assertEqual(fake.sent, [("PATCH", f"repos/{REPO}/issues/comments/2")])
        self.assertEqual(fake.body(2), NEW_REPORT)
        self.assertEqual(len(fake.comments), 3)

    # AI-written: a person's comment that contains the marker is never
    # edited; only the bot's own comments count.
    def test_marker_in_a_persons_comment_is_ignored(self):
        fake = FakeGitHub(("mallory", "quoting the bot: " + REPORT))
        self.run_post(fake, NEW_REPORT)
        self.assertEqual(fake.sent[0][0], "POST")
        self.assertEqual(fake.body(1), "quoting the bot: " + REPORT)

    # AI-written: other comments by the same bot account, without the marker,
    # are left alone too.
    def test_bot_comment_without_marker_is_ignored(self):
        fake = FakeGitHub((BOT_LOGIN, "Some other workflow's comment"))
        self.run_post(fake, NEW_REPORT)
        self.assertEqual(fake.sent[0][0], "POST")

    # AI-written: with several bot comments from before C8, the newest one is
    # updated.
    def test_newest_of_several_bot_comments_is_updated(self):
        fake = FakeGitHub((BOT_LOGIN, REPORT), ("alice", "/review"), (BOT_LOGIN, REPORT))
        self.run_post(fake, NEW_REPORT)
        self.assertEqual(fake.sent, [("PATCH", f"repos/{REPO}/issues/comments/3")])
        self.assertEqual(fake.body(1), REPORT)

    # AI-written: the bot's comment is found past the first page of 100.
    def test_comment_on_second_page_is_found(self):
        fake = FakeGitHub(*[("alice", f"comment {i}") for i in range(100)], (BOT_LOGIN, REPORT))
        self.run_post(fake, NEW_REPORT)
        self.assertEqual(fake.sent, [("PATCH", f"repos/{REPO}/issues/comments/101")])

    # AI-written: a body without the marker, such as a dry-run summary, gets
    # it on top, so the next review finds and edits that comment too.
    def test_marker_is_added_when_missing(self):
        fake = FakeGitHub()
        self.run_post(fake, "## 🤖 PR review: dry run\n")
        self.assertEqual(fake.body(1), MARKER + "\n## 🤖 PR review: dry run\n")
        self.run_post(fake, REPORT)
        self.assertEqual(fake.sent[-1], ("PATCH", f"repos/{REPO}/issues/comments/1"))

    # AI-written: a failed run puts a note with the run link on top and keeps
    # the last review below it.
    def test_failure_keeps_the_previous_review(self):
        fake = FakeGitHub((BOT_LOGIN, REPORT))
        self.run_post(fake, run_url=RUN_1)
        body = fake.body(1)
        self.assertTrue(body.startswith(MARKER))
        self.assertIn("The latest review failed", body)
        self.assertIn(RUN_1, body)
        self.assertIn(post_comment.KEPT.strip(), body)
        self.assertIn("- [ ] **Issue link:** No issue is linked.", body)
        self.assertEqual(body.count(MARKER), 1)

    # AI-written: failing several times in a row leaves one note, with the
    # newest run link, and still one comment.
    def test_repeated_failures_replace_the_note(self):
        fake = FakeGitHub((BOT_LOGIN, REPORT))
        self.run_post(fake, run_url=RUN_1)
        self.run_post(fake, run_url=RUN_2)
        body = fake.body(1)
        self.assertEqual(body.count("The latest review failed"), 1)
        self.assertIn(RUN_2, body)
        self.assertNotIn(RUN_1, body)
        self.assertIn("No issue is linked.", body)
        self.assertEqual(len(fake.comments), 1)

    # AI-written: the next successful review replaces the whole comment, so
    # the failure note is gone.
    def test_success_after_failure_removes_the_note(self):
        fake = FakeGitHub((BOT_LOGIN, REPORT))
        self.run_post(fake, run_url=RUN_1)
        self.run_post(fake, NEW_REPORT)
        self.assertEqual(fake.body(1), NEW_REPORT)

    # AI-written: a failure on a PR the bot never commented on posts only the
    # note, without saying a previous comment is kept.
    def test_failure_without_a_previous_comment(self):
        fake = FakeGitHub()
        self.run_post(fake, run_url=RUN_1)
        body = fake.body(1)
        self.assertIn(RUN_1, body)
        self.assertNotIn(post_comment.KEPT.strip(), body)


if __name__ == "__main__":
    unittest.main()
