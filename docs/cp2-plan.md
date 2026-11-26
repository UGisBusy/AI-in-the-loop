# CP2 plan, Group 24

State: Thu 26 Nov 2026. Due Sun 29 Nov, 23:59 Taipei, one zip `Group24_CP2` on E3. Owners and dates are proposals.

**Decision 26 Nov:** CP2 finishes the current prototype from #9. The sandbox reviewer comes after CP2.

**Each of us by Sunday:** 2 merged PRs with substantive code, 2 steward approvals with a real comment, steward once in DECISIONS.md.

**Rubric:** product 50 (prototype 15, design and user tests 10, AI components 15, evaluation 10), collaboration 50 (code from all four 15, reviews 15, DECISIONS.md 10, sessions 10).

| Workstream | Owner | In one line |
| --- | --- | --- |
| C. Code | Everyone | Two polish PRs each on top of #9 |
| D. Docs | UG, sohanksome, heyvrann | Prompt card, design rationale with 2 user tests, evaluation report |
| S. Sessions | Steward of the day | Rotation, walking skeleton, merge day, DECISIONS.md |

## Checklist

- [ ] **C1** Merge #9 | UG | Thu 26
  - Done when: a real `/review` runs from main.
- [ ] **C2** Reject repeated results for a point | Daniel | Thu 26
  - Done when: two results for one point stop the review, tests pass.
- [ ] **C3** Check filled sections in Python | Daniel | Fri 27
  - Done when: Summary, Verification and Synthetic prompt are checked without Claude, tests pass.
- [ ] **C4** `--save-context` and `--context-file` | sohanksome | Fri 27
  - Done when: a saved context gives the same prompt without GitHub calls.
- [ ] **C5** Prompt suite runner, 10 frozen PRs with expected results | sohanksome | Sat 28
  - Done when: the runner lists mismatches per point, and one fail, fix, re-run is recorded.
- [ ] **C6** Pass/fail rule per criterion and 3x repeat runs, closes #11 | UG | Fri 27
  - Done when: the output shows agreement per point over 3 runs.
- [ ] **C7** Tokens and cost in report.json, for #12 | heyvrann | Fri 27
  - Done when: report.json holds input tokens, output tokens and USD.
- [ ] **C8** Re-review updates the existing comment | heyvrann | Sat 28
  - Done when: a second `/review` edits the first comment.
- [ ] **D1** CLAUDE.md and prompt card | UG | Fri 27
  - Done when: role, instructions and known failure modes are written down.
- [ ] **D2** AI guidelines, merge #15 | UG | Fri 27
- [ ] **D3** Design rationale with 2 user tests outside the team | sohanksome | Sat 28
- [ ] **D4** Interim evaluation report, honest about what is untested | heyvrann | Sat 28
- [ ] **S1** Steward rotation: Daniel Thu, UG Fri, sohanksome Sat morning, heyvrann Sat afternoon, each in DECISIONS.md
- [ ] **S2** Walking skeleton: merged PR link and docs/walking_skeleton.md | all | Fri 27
- [ ] **S3** Merge day: plan in DECISIONS.md before, docs/merge_day.md after, fresh clone by a non-steward | steward | Sat 28
- [ ] **S4** DECISIONS.md: date, what, why, rejected option, leader for every decision | all
- [ ] **S5** Contributor graph screenshot, zip with repo link .txt, E3 upload | Daniel | Sun 29, 20:00
