---
Date: 2026-07-12
Author: Release Manager (Claude)
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: Rollback guide for the System2 Completion Mission (Production Hardening Sprint). Updated as each phase lands.
---

# Rollback Guide

One section per phase that touched code or config. Docs-only phases are not
listed here (nothing to roll back beyond deleting a markdown file, which
carries no runtime risk).

## Phase 2 — Duplicate-order prevention

**Files modified:**
- `execution/execution_state.py` — added `build_intent_identity()` (new pure
  function), `ExecutionStateStore.find_active_by_identity()` (new method).
  No existing function/method modified.
- `execution/trade_manager.py` — modified `open_position()`: replaced the ad
  hoc `signal_id` f-string with a call to `build_intent_identity()`, and
  inserted a duplicate-check block before `create_record()`. No other method
  changed.
- `tests/execution/test_duplicate_order_prevention.py` — new file, 21 tests.
- `tests/execution/test_trade_manager.py` — fixed a pre-existing test-
  isolation bug (`_make_manager()` now uses an isolated temp-directory store
  instead of the shared default `ExecutionStateStore(".")`); one test
  updated to reuse that isolated store when reconstructing a second
  `TradeManager` instance.

**Database changes:** none.

**Migration impact:** none.

**Rollback commands:**
```bash
git revert <phase-2-commit-sha>
```
A clean revert is possible because every change is additive or test-only —
no existing function signature changed shape, no existing state-machine
transition changed, no config changed.

**Risk if reverted:** returns to the pre-Phase-2 state — `open_position()`
places an order for every call with no duplicate check, i.e. the exact gap
`SYSTEM2_CORRECTNESS_AUDIT.md` identified. Acceptable only as an emergency
rollback (e.g. if the identity/dedup logic itself were found to incorrectly
block legitimate trades in production) — the `test_different_signals_are_not_deduped_false_positive_check`
test exists specifically to catch that failure mode before merge, so a
post-merge false-positive would indicate a gap in that test, not an expected
outcome.

**Verification after rollback:** `python -m pytest tests/execution
tests/production tests/scripts -q` should return to the pre-Phase-2 baseline
(145 passed, per `PHASE1_REPOSITORY_STATE.md`'s verification run).

---

*(Further phases append their own section below as they land.)*
