# Written by AI (Claude Opus 5.5 in Claude Code). Run with:
#     python -m unittest discover -s bot

import unittest

from claude_review import ReviewError, order_results
from report import VERDICT_FAIL, VERDICT_PASS, load_parts, render

PARTS = load_parts()
IDS = [point["id"] for part in PARTS for point in part["points"]]


def result(point_id, status="pass"):
    return {"id": point_id, "status": status, "explanation": "x", "requested_change": "" if status == "pass" else "y"}


def report(criteria):
    return {"head_sha": "0" * 40, "requested_by": "test", "criteria": criteria}


class OrderResultsTest(unittest.TestCase):
    # AI-written: a complete answer comes back in criteria.json order and renders.
    def test_complete_answer_in_criteria_order(self):
        returned = [result(i) for i in reversed(IDS)]
        ordered = order_results(PARTS, returned)
        self.assertEqual([r["id"] for r in ordered], IDS)
        self.assertIn(VERDICT_PASS, render(report(ordered)))

    # AI-written: a missing point is an error, not a silent pass.
    def test_missing_point_fails(self):
        with self.assertRaisesRegex(ReviewError, "no result for: " + IDS[-1]):
            order_results(PARTS, [result(i) for i in IDS[:-1]])

    # AI-written: a repeated point stops the review in any order, also when both
    # results agree, so no verdict depends on which result came first.
    def test_repeated_point_fails_in_any_order(self):
        rest = [result(i) for i in IDS[1:]]
        for first, second in (("pass", "fail"), ("fail", "pass"), ("pass", "pass")):
            with self.subTest(first=first), self.assertRaisesRegex(ReviewError, "more than one result for: " + IDS[0]):
                order_results(PARTS, [result(IDS[0], first), result(IDS[0], second), *rest])

    # AI-written: a failed point still yields "Changes requested".
    def test_failed_point_requests_changes(self):
        ordered = order_results(PARTS, [result(IDS[0], "fail"), *[result(i) for i in IDS[1:]]])
        self.assertIn(VERDICT_FAIL, render(report(ordered)))


if __name__ == "__main__":
    unittest.main()
