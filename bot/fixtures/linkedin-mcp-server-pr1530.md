## Summary

- `get_feed` scrolled up to a fixed 12 times, waiting up to ~12 s per scroll, with no way for a caller to trade posts for time.
- `max_scrolls` (1-12) now lowers the scroll cap. The default stays 12, since a scroll can wait up to ~12 s and more would run past the 180 s tool timeout.
- Passed through `LinkedInExtractor.extract_feed` to the feed reader, the same way `get_company_posts` takes `max_scrolls` (#1104). Continuing a partial read, the other half of #1406, is left out.
- Closes #1406.

## Verification

- `test_max_scrolls_lowers_the_ceiling` in `tests/linkedin/test_feed.py` scripts one batch per wheel and checks the loop stops at 3 wheels. The tool and facade tests check the value is passed through and that 0 and 13 are refused. Dropping it at the tool, the facade or the reader, or widening the cap, each fails a test.
- `facade-contract.json` and `tools.json` are regenerated for the new parameter.
- Full suite run serially without browser tests: 9379 passed. ruff, ty, the policy-trace check and the architecture check pass.

## Synthetic prompt

> get_feed scrolls a fixed 12 times. Add an optional max_scrolls (1-12, default 12) to the tool, pass it through LinkedInExtractor.extract_feed to the feed reader's scroll loop, regenerate the contract fixtures, and cover it in tests.

Implemented with Claude Opus 5.5 (high) in Claude Code via Terminal.


