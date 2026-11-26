# Decisions Log

## 2026-09-24 — Initial code steward
**What:** Daniel Sticker (stickerdaniel) is the initial code steward for the team.
**Why:** Volunteered for the first rotation.

## 2026-11-21 — GH action to activate bot review
**Why:** No backend required, easy to setup
Alternative rejected: Host backend sever (python Fast API or some JS stuff)
Led by: UGisBusy

## 2026-11-21 — Only allowed user can request bot review
**Why:** Prevent burning tokens from spamming reviews
Alternative rejected: auto-review on every PR push, or letting anyone (including the pr author) trigger it
Led by: UGisBusy

## 2026-11-21 — Store API key in the GH repo secret
**Why:** To make GH action able to access it, though this introduce some issues:
1. Everyone with write access can read it
2. Any PR code that runs in the same job could read and leak the key, so the job never runs PR code
3. Review bot users can still spam requests
Alternative rejected: avoid this if we're using backend sever approach
Led by: UGisBusy
