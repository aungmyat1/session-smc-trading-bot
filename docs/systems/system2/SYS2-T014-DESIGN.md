# SYS2-T014 — Architecture Design Package

Date: 2026-07-07
Status: **COMPLETED — merged to `main` via PR #27** (`d140783`). See §10 for
the implementation result and §11 for the merge/release record.
Original scope: `execution/trade_manager.py` and its two confirmed failure
paths (risk-register #14, `docs/audit/execution-record-nonterminal-investigation.md`)
Owner: Architecture review (this document) → implemented per handoff → merged
Exit criteria: state machine approved, DB impact classified, tests specified,
rollback plan defined — all four addressed below.

---

## 1. Key finding: the reconciliation logic already exists and is already
##    evidence-based — this is a wiring gap, not a missing design

Before proposing anything new, I read the actual state machine
(`execution/execution_state.py`), the actual live hot path
(`execution/trade_manager.py`), and the actual reconciliation code
(`execution/startup_recovery.py`). This changes the shape of the fix
materially from what a from-scratch design would assume:

- `execution/execution_state.py` already defines a real, BFS-validated state
  machine (`_ALLOWED_TRANSITIONS`), not an ad hoc one. `BROKER_ACKNOWLEDGED`
  already legally allows `{PARTIALLY_FILLED, FILLED, JOURNALED, RECONCILED,
  FAILED_TERMINAL}`. The problem was never a missing transition — it's that
  **nothing in the normal (non-crash) code path ever invokes one**.
- `execution/startup_recovery.py::reconcile_pending_executions()` **already
  is** the evidence-based reconciliation worker the generic design template
  would ask us to build: it takes a live broker-positions snapshot, and for
  each incomplete `ExecutionRecord`:
  - If `broker_order_id` is already known → ensures a journal row exists,
    then advances the record to `COMPLETED` (evidence: broker acknowledged
    the order — proven by `broker_order_id` being set at all).
  - If no `broker_order_id` yet → searches live open positions for an
    unlinked match on symbol/direction/lots (evidence: a live broker
    position, not just "no error was thrown"). Match found → adopt it,
    backfill the journal, advance to `COMPLETED`. No match → advance to
    `FAILED_TERMINAL` with an explicit "signal lost, not resubmitted" note.
  - This already satisfies the instruction "do not allow 'successful broker
    response' alone unless the architecture confirms that is sufficient" —
    the function never trusts a bare successful response; it always
    re-checks against a live broker-positions snapshot before advancing.
- **The only actual defect**: this function is called exactly once, at
  process startup (`scripts/run_st_a2_demo.py:927`), never again during the
  `while True:` tick loop (`scripts/run_st_a2_demo.py:976-995`). Every
  successful order placement's `BROKER_ACKNOWLEDGED` record sits there until
  the next restart; every `RECOVERY_PENDING` record sits there until the
  next restart. That's the entire root cause.

**Conclusion: this is Option A (periodic reconciliation) — already built as
a reusable function, just not invoked periodically.** No new reconciliation
architecture needs to be designed. The task is to call an existing,
already-reviewed function on a schedule, not to invent Option A or Option B
from scratch.

---

## 2. State machine clarification (exit criterion 1)

```
SUBMISSION_PENDING
      |
      v
BROKER_ACKNOWLEDGED  (evidence: broker returned an order_id — trade_manager.py:151)
      |
      | [existing gap: nothing calls this next step outside startup]
      v
reconcile_pending_executions() periodic call
      |
      +---- broker_order_id known, journal ensured -> COMPLETED
      |       (evidence: journal row backfilled/confirmed against broker fact)
      |
      +---- no broker_order_id, live position match found -> COMPLETED
      |       (evidence: matching open broker position, symbol+direction+lots)
      |
      +---- no broker_order_id, no match -> FAILED_TERMINAL
              (evidence: absence of any broker position after a live check —
               signal treated as lost, never resubmitted)

RECOVERY_PENDING (ambiguous error: timeout/no-response, trade_manager.py:161-165)
      |
      v
same reconcile_pending_executions() call, same rules as above
```

**Answering the evidence question directly**: the transition out of
`BROKER_ACKNOWLEDGED`/`RECOVERY_PENDING` is never driven by "successful
broker response" alone — it requires a fresh live-position query
(`manager.get_positions()`) at reconciliation time, cross-referenced against
`TradeJournalDB.get_broker_order_ids()`. This is already Option A's
"Broker State Check" step in the generic template, already implemented.

---

## 3. RECOVERY_PENDING design decision (exit criterion — open, not yet resolved)

One real design gap the existing startup-only code doesn't have to answer,
but a periodic call does: **timing risk**. `startup_recovery.py`'s docstring
assumes it runs only after a full process restart, when any order that
timed out has had ample time (the outage duration) to either land at the
broker or definitely fail. A periodic in-tick-loop call could run seconds
after a timeout, while the order might still be in flight at the broker —
reconciling too early risks marking a record `FAILED_TERMINAL` for an order
that lands moments later, contradicting the "signal lost, not resubmitted"
guarantee (the position would then be orphaned: open at the broker, marked
lost in our records).

**Recommendation**: gate periodic reconciliation on record age, e.g. only
attempt to resolve a `RECOVERY_PENDING`/stale-`BROKER_ACKNOWLEDGED` record
once `now - updated_at` exceeds a threshold (propose 60s, double the
existing exponential-backoff retry window in `trade_manager.py`'s
`_ORDER_RETRY_ATTEMPTS`/`_ORDER_RETRY_BASE_DELAY_S`, so periodic
reconciliation never races the retry loop itself). This is a genuine open
decision for whoever implements this — not resolved by this document, since
picking the exact threshold is an implementation detail, not an
architecture question. Flagged, not decided.

**BROKER_ACKNOWLEDGED with a known `broker_order_id` does not have this
timing risk** — the "ensure journal, advance to COMPLETED" branch is safe to
run immediately, since it only ever adds information (a journal row), never
concludes the order failed.

---

## 4. Database impact assessment (exit criterion 2) — **no migration required**

Checked both persistence layers this touches:

- **`ExecutionStateStore`** (`execution/execution_state.py`) is JSON-file-backed
  (`data/execution/*.json`), not a Postgres table. `ExecutionRecord` already
  carries `state`, `updated_at`, `broker_order_id`, `state_history` — every
  field the reconciliation logic and the age-gate in §3 need. **No new field
  required** — `updated_at` already updates on every `transition()` call, so
  the age-gate in §3 needs zero schema change.
- **Postgres `operations.*` schema** (Sprint 2.3, `execution/operations_recorder.py`):
  `record_recovery_checkpoint()` and `record_reconciliation()` already exist
  and are already called by the one existing (startup) reconciliation call
  site (`scripts/run_st_a2_demo.py:927-928`). A periodic call reuses these
  same functions — it just writes more rows to a table that already models
  "a reconciliation happened" generically. **No new column, no new table.**

**Verdict: Case 1 (existing fields sufficient) — no DB migration task
needed for this fix**, contrary to the generic template's assumption that
migration status was unknown. If a future implementer finds they need
`recovery_attempt_count` for the age-gate in §3, `state_history` already
carries a full timestamped event list per record — a count is derivable
from existing data without a schema change (count `RECOVERY_PENDING` entries
in `state_history`), so even that doesn't obviously require new storage.

---

## 5. Implementation checklist (for the eventual Developer Agent — not authorized yet)

1. Add a periodic call to `reconcile_pending_executions(execution_store,
   _journal_db, await manager.get_positions())` inside the `while True:`
   tick loop (`scripts/run_st_a2_demo.py:976-995`), not just at startup
   (line 927) — e.g. every N ticks (N to be chosen against the existing
   `interval` parameter, so this doesn't fetch positions every single tick
   if that's too chatty against the broker).
2. Apply the age-gate from §3 before calling reconciliation on any given
   record — do not reconcile a record younger than the chosen threshold.
   `ExecutionStateStore` already exposes `updated_at`; filtering belongs in
   the caller (`run_st_a2_demo.py`) or as a new optional parameter on
   `recover_incomplete()`/`reconcile_pending_executions()` — an
   implementation choice, not decided here.
3. Continue calling `ops_recorder.record_recovery_checkpoint(...)` after
   each periodic reconciliation pass, exactly as the startup call already
   does — no new recording code needed.
4. Do **not** modify `_ALLOWED_TRANSITIONS`, `_classify_error()`, or the
   `ambiguous`/`transient`/`terminal` classification in `trade_manager.py` —
   all already correct and explicitly protected (§0 constraint below).

---

## 6. Test specification (exit criterion 3)

Building on the existing test files (`tests/execution/test_trade_manager.py`,
`tests/execution/test_startup_recovery.py`, `tests/execution/test_reconcile_positions.py`
already cover the startup-only path):

1. **Periodic resolution, `BROKER_ACKNOWLEDGED` branch**: an `ExecutionRecord`
   at `BROKER_ACKNOWLEDGED` with a real `broker_order_id`, reconciled
   mid-session (no restart) → advances to `COMPLETED`, journal row
   confirmed/backfilled exactly once.
2. **Periodic resolution, `RECOVERY_PENDING` branch, match found**: a record
   at `RECOVERY_PENDING` with no `broker_order_id`, a live position matching
   symbol/direction/lots exists → advances to `COMPLETED`, adopts the
   discovered order id.
3. **Periodic resolution, `RECOVERY_PENDING` branch, no match, past the
   age-gate** → advances to `FAILED_TERMINAL`, signal marked lost, no
   resubmission attempted (assert `place_order`/`open_position` never called
   again for this record).
4. **Age-gate holds a young record** — a `RECOVERY_PENDING` record younger
   than the threshold is *not* touched by a reconciliation pass (still
   `RECOVERY_PENDING` afterward) — protects against the timing risk in §3.
5. **Duplicate reconciliation / idempotency** — running reconciliation twice
   in a row against the same already-`COMPLETED` record is a no-op (already
   structurally guaranteed: `recover_incomplete()` filters `TERMINAL_STATES`,
   so a resolved record simply won't be reprocessed — this test proves the
   existing guarantee still holds once the call becomes periodic, not a new
   mechanism).
6. **Timeout-ambiguity preservation** — `trade_manager.py:196-200`'s
   `_classify_error()` output (`"ambiguous"` for timeout/no-response/unknown
   execution state) must be unchanged by this work; add a regression test
   asserting the same inputs produce the same classification after the
   periodic-reconciliation change lands.
7. **Full regression**: `tests/execution/` (124+ tests, includes the 3 files
   above), `tests/scripts/test_run_st_a2_demo_close_detection.py`, and the
   dashboard suite that reads execution state via `operations_recorder`.

---

## 7. Rollback plan

Additive change only — a new periodic call site plus (optionally) an
age-gate parameter. No existing transition, classification, or schema is
modified. Revert is a single-commit `git revert` of the tick-loop wiring
change. If the age-gate proves wrong in practice (too aggressive or too
conservative), it's a one-line threshold adjustment, not a design change.

---

## 8. Constraints carried forward (unchanged, enforced)

No ExecutionService changes. No FIX API work. No broker abstraction changes.
No DB migration (confirmed unnecessary, §4). Preserve
`trade_manager.py:196-200`'s existing timeout-ambiguity classification
exactly (§6 test 6 makes this a regression-tested guarantee, not just a
stated intent).

---

## 9. Architecture verdict

**APPROVED for implementation planning**, with one explicit open decision
left for the implementer: the exact age-gate threshold (§3). Everything
else in this package is grounded directly in existing, already-reviewed code
— this is a scope-reduction finding as much as a design package: the actual
implementation is smaller than "build a reconciliation architecture," it is
"invoke an existing, correct reconciliation function on a schedule, with one
new timing safeguard." Route to Developer Agent for a single, isolated
commit implementing §5, gated on this document's test spec (§6) passing
before any shadow-verification against the live `smc-demo-runner.service`.

---

## 10. Implementation result (2026-07-07)

Implemented exactly per §5, with the age-gate threshold decision (§3)
resolved as **60 seconds** (`RECONCILE_MIN_PENDING_AGE_S`, configurable),
double the existing `_ORDER_RETRY_BASE_DELAY_S`-based exponential backoff
window so periodic reconciliation never races the retry loop.

**Files changed:**
- `execution/startup_recovery.py` — added `min_pending_age_seconds` keyword
  parameter (default `0.0`, preserving the original startup-only call site's
  behavior byte-for-byte) to `reconcile_pending_executions()`, plus
  `_past_age_gate()`. A record with no `broker_order_id` yet and younger than
  the gate is skipped for *resolution*, but is still read-only matched
  against open positions (reusing the existing `_find_unlinked_match()`) so
  its position isn't misreported as orphaned while it waits out the gate — no
  new architecture, just closing a false-positive-noise gap the gate would
  otherwise introduce. A record with a known `broker_order_id`
  (`BROKER_ACKNOWLEDGED`) is never gated, per §3's reasoning.
- `scripts/run_st_a2_demo.py` — added `RECONCILE_EVERY_N_TICKS` (default 5,
  `0` disables periodic reconciliation entirely) and
  `RECONCILE_MIN_PENDING_AGE_S` (default 60) as env-configurable module
  constants; added `_should_run_periodic_reconciliation()` (a pure function,
  deliberately factored out of the tick loop so it's unit-testable without
  the broker/runtime stack) and `_reconcile_periodic()` (calls the same
  `reconcile_pending_executions()` + `ops_recorder.record_recovery_checkpoint()`
  pairing the existing startup-recovery block already uses); wired into the
  `while True:` loop right after each `_tick()` call. The one-shot startup
  recovery call site (`run()`, before the loop) is untouched.
- `tests/execution/test_startup_recovery.py` — 4 new tests: age-gate defers a
  young no-`broker_order_id` record without orphaning its matching position;
  resolves it once old enough; never gates a known-`broker_order_id` record
  regardless of age; default (no kwarg) behavior matches pre-SYS2-T014
  exactly.
- `tests/scripts/test_run_st_a2_demo_periodic_reconciliation.py` (new) — the
  4 required regression areas: periodic-execution policy (6 cases),
  duplicate reconciliation across repeated periodic-style calls, timeout-
  ambiguity preservation (asserts `trade_manager.py`'s ambiguous-error
  classification still parks a timed-out order at `RECOVERY_PENDING` with no
  `broker_order_id`), and a signature-lock test guarding the startup call
  site's backward compatibility.
- No changes to `trade_manager.py`, `execution_state.py`'s
  `_ALLOWED_TRANSITIONS`, or any database schema/migration.

**Test results:** 28 tests in the 3 directly-relevant files (all new/updated
tests plus the full pre-existing `test_trade_manager.py` suite), plus the
full `tests/execution/` + `tests/scripts/` regression sweep — **162 passed,
0 failed**. (`tests/test_status_server.py` was excluded from the sweep: it
fails to collect due to a pre-existing, unrelated `NameError` in
`dashboard/status_server.py` — confirmed via `git diff HEAD` to already be
on `main` before this work, not introduced by it.)

**Not committed [superseded, see §11]:** the above described the state
before isolation/commit. §11 records what actually happened.

---

## 11. Merge & release record (2026-07-07)

- **Isolated commit**: `scripts/run_st_a2_demo.py` had substantial unrelated
  pre-existing uncommitted work (`RiskPortfolioStore`, `ValidationSessionManager`,
  migration 005/006 wiring) co-resident in the same file. Isolation was
  performed by reconstructing the file from clean `HEAD` plus exactly the
  SYS2-T014 edits, independently re-verified byte-for-byte against a
  from-scratch reconstruction before staging — not a whole-file commit.
- **PR**: opened from a fresh branch (`sys2-t014-periodic-reconciliation`,
  based on `origin/main`) rather than the long-lived working branch, to avoid
  re-displaying already-merged history as new — [#27](https://github.com/aungmyat1/session-smc-trading-bot/pull/27).
- **CodeRabbit finding (fixed same-day)**: periodic reconciliation logged
  recovered/lost outcomes but didn't alert via Telegram, unlike the startup
  path handling the identical event. Fixed to match (`b6ba38f`).
- **CI**: all required checks passed (unit, integration, quality/architecture,
  security, docs/package contracts, CodeRabbit). Zero unresolved review
  threads at merge time.
- **Merged**: squash merge, commit `d140783f51f030292cd461131ef334ce11051d0a`,
  2026-07-07T16:20:17Z. Merge commit diff confirmed to contain exactly the
  5 SYS2-T014 files (611 insertions, 1 deletion) — no anomaly.
- **Post-merge verification**: `main` compiles; `tests/architecture` (15/15),
  `check_docs_drift.py`, and CI's exact unit-tier command (241/241 at the
  real merged tip — the `RiskPortfolioStore`/validation WIP's own test files
  inflated an earlier working-tree-only count to 292; not part of this merge)
  all pass.
- **Branch `sys2-t014-periodic-reconciliation`**: not deleted post-merge
  (no `--delete-branch` used); low-priority cleanup, not performed
  unilaterally.
- **Follow-up tasks** (not implemented, tracked for future work): SYS2-T015
  (CI coverage for `tests/scripts/`), SYS2-T016 (log-message differentiation
  for periodic-reconciliation errors), SYS2-T017 (scheduler operational
  documentation), SYS2-T018 (integration test for orphan-suppression during
  the age-gate window).
