Closes #1324

## Summary

Adds `start` to `search_jobs`: the result offset of the search's first page, `0` by default. Passing back a previous call's `pagination.next_offset`, with the same search arguments, continues a search that `max_pages` or the time budget cut short, without fetching its earlier pages again.

- The first page is requested at `start` and held to it by the offset check that already guards every later page.
- A resumed search that lands on LinkedIn's recommendations page has run past the end of a list an earlier call read results from. It answers `pagination.reason: complete` with no `no_matching_jobs` entry, as a search does when recommendations follow real results.
- The returned `url` carries `&start=<n>` when `start` is not `0`, so it names the page the call read first.
- `start` is validated as `ge=0` by the tool schema. The docstring says that results can shift between calls, so a continuation may repeat a job id.

Documented in the tool docstring and the `pagination` entry in `AGENTS.md`. The README tool table is unchanged.

## Live evidence

On the classic search page, 2026-09-26: a search with `max_pages=1`, then the same arguments with `start=10`. The two calls read offsets 10 apart, ten job ids each, none shared, and no `section_errors`. The returned `url` of the second call did not name its offset then, which the second commit fixes. The redesigned `/jobs/search-results/` page keeps `start` in its address (#1361); a resumed search there has not been measured separately. Nothing was rerun live on this exact commit.

## Verification

- `tests/linkedin/test_jobs.py`: a resumed search requests its first page at `start`, advances from it and returns that page's `url`; a first page served without the offset stops the search instead of repeating the previous call; a resumed search reaching recommendations is complete with no `no_matching_jobs`.
- `tests/test_tools.py`: the tool passes `start` on to the extractor.
- The tool contract, the facade contract and its policy trace were regenerated. `ruff`, `ty` and the architecture check pass.
- Full suite in fork CI on a build carrying this head (`d391b98e`): every job passed, the `test` job included.

## Synthetic prompt

> Add a `start: int = 0` argument (schema `ge=0`) to `search_jobs`, threaded through the extractor facade into `JobReader.search_jobs`, as the offset of the first page requested, so a caller can pass back `pagination.next_offset` to continue a stopped search. Seed the running offset from it so the existing per-page offset check also guards the first page. When a search started at a non-zero offset reaches LinkedIn's recommendations page with no results yet, end it as `complete` without the `no_matching_jobs` section error. Make the returned `url` include `&start=<n>` for a resumed search. Document the argument in the tool docstring and in `AGENTS.md`'s `pagination` entry, add workflow and tool tests, and regenerate the tool contract, facade contract and policy traces.

Implemented with Claude Opus 5.5 (high) in Claude Code via tmux.


<!-- Macroscope's pull request summary starts here -->
<!-- Macroscope will only edit the content between these invisible markers, and the markers themselves will not be visible in the GitHub rendered markdown. -->
<!-- If you delete either of the start / end markers from your PR's description, Macroscope will append its summary at the bottom of the description. -->
> [!NOTE]
> ### Add `start` offset parameter to `search_jobs` for resuming searches
> - `JobReader.search_jobs` accepts a `start` result offset and includes it in the returned URL when nonzero ([jobs.py](https://github.com/stickerdaniel/linkedin-mcp-server/pull/1521/files#diff-3d5f3d6e509a6bb940aaf62e68c4aa0df25c475f41e7b28c617319f350dc6d1e)).
> - The offset flows through `LinkedInExtractor.search_jobs` and the MCP `search_jobs` tool handler, which documents passing `pagination.next_offset` as `start` to continue a search ([job.py](https://github.com/stickerdaniel/linkedin-mcp-server/pull/1521/files#diff-d820972b590e99f80b87441f5f043b95bbeff4d75cd67bd1cfc39d283d250919), [extractor.py](https://github.com/stickerdaniel/linkedin-mcp-server/pull/1521/files#diff-c4a11f174d3d8396adfae9ffc1cabea47536d0bc3f84e8f45c3bcb71007bdeba)).
> - Adds tests for resuming from an offset, stopping with `pagination_stopped` when the landed URL lacks the offset, and completing when a resumed search reaches a recommendations page.
> - Behavioral Change: if navigation lands on a URL without the requested offset, the search now stops with a `pagination_stopped` error instead of continuing.
>
> <!-- Macroscope's review summary starts here -->
>
> <sup><a href="https://app.macroscope.com">Macroscope</a> summarized d391b98.</sup>
> <!-- Macroscope's review summary ends here -->
>
<!-- Macroscope's pull request summary ends here -->

