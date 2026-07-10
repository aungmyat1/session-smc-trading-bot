# Investigation: 58 Unexplained Non-Terminal ExecutionRecords

Date: 2026-07-07
Status: Root cause identified — code-path confirmed and independently
re-verified against archived data. Read-only investigation; no code changed.
Related: `docs/systems/system2/STATUS.md` (origin of the "58" figure),
`docs/svos/PHASE-5B5-ARCHITECTURE-APPROVAL.md` §7.1 (flagged this as a
Phase 5C precondition without investigating it — this document closes that gap)

## Origin

`docs/systems/system2/ROADMAP.md` Phase 12 ("Extended Demo Validation"):
"119 MetaAPI subscription-timeout errors and 58 unexplained non-terminal
`ExecutionRecord`s found, not yet root-caused."

## Method

Delegated to `execution-agent` for code-path analysis, then independently
re-verified the agent's data claims myself (the agent's first-pass numbers
matched exactly on re-check using correct JSON field extraction — see
Verification section).

## Root cause (confirmed)

Two independent, compounding causes:

**1. `BROKER_ACKNOWLEDGED` has no forward transition anywhere in the live
code path.** `execution/execution_state.py:23` legally allows
`BROKER_ACKNOWLEDGED → {PARTIALLY_FILLED, FILLED, JOURNALED, RECONCILED,
FAILED_TERMINAL}`, but `execution/trade_manager.py`'s `open_position()` sets
a record to `BROKER_ACKNOWLEDGED` (`:151`) after a successful broker
response and then returns — nothing in `trade_manager.py` or its caller
(`scripts/run_st_a2_demo.py:_execute_via_manager`) ever advances the record
further. The transition is *allowed* by the state machine but never *invoked*
by any code that runs during normal operation. This is a structural gap, not
a timeout-dependent one.

**2. MetaAPI timeouts during order placement park records at
`RECOVERY_PENDING`, which only clears at process startup.**
`trade_manager.py:186` classifies ambiguous errors (`"timeout"`, `"timed out"`,
`"no response"`, `"unknown execution state"`) by pushing the record to
`RECOVERY_PENDING` and re-raising. The only code that ever resolves
`RECOVERY_PENDING` records is `execution/startup_recovery.py`'s
`reconcile_pending_executions()`, called exactly once, before the tick loop
starts (`scripts/run_st_a2_demo.py:927` — confirmed single call site, no
other invocation found in `execution/*.py` or `scripts/run_st_a2_demo.py`).
`docs/systems/system2/ROADMAP.md` itself records "0 restarts" for the
observed window — meaning reconciliation ran once at boot and never again
during the ~2-day validation period. Any record entering
`RECOVERY_PENDING` mid-session has no in-process path to a terminal state
until the next restart.

## Verification (independent re-check, not just re-quoting the agent)

The agent additionally found a data point: `/home/aungp/archives/data-execution-test-pollution-2026-07-06/`
(376 `ExecutionRecord` JSON files). I independently re-extracted the
**top-level** `state` field via direct JSON parsing (my first manual check
used a naive `grep` that matched substrings inside each file's
`state_history` array too, producing wrong, inflated, overlapping counts —
corrected before trusting the result):

```
COMPLETED         218
FAILED_TERMINAL   100
BROKER_ACKNOWLEDGED 40
RECOVERY_PENDING    18
                  ---
total             376
```

`40 + 18 = 58` — matching the ROADMAP's figure exactly.

**Caveat, preserved honestly**: this archived directory is dated
2026-07-06, named `data-execution-test-pollution`, and its provenance
relative to the actual VPS `data/execution/` store behind the ROADMAP's
"58" figure is not confirmed — the match is a strong, suggestive
independent data point for the same failure mechanism, not proof it is
literally the same 58 records. The live VPS `data/execution/` directory
was not checked in this pass (recommend doing so to close this gap fully).

## Disposition

Both causes are code-path defects in `execution/trade_manager.py`
specifically (not `order_manager.py`, `vantage_demo_executor.py`, or the
risk engine) — this narrows, rather than widens, the scope of any future
fix, and is consistent with `trade_manager.py` already being identified as
the highest-priority ExecutionService migration target
(`docs/svos/PHASE-5B5-ARCHITECTURE-APPROVAL.md` §5). **No fix is proposed or
implemented here** — this document is the investigation Phase 5C asked for,
not a Phase 5C implementation.

## Recommendation

1. Treat this as resolved-for-documentation-purposes (root cause identified,
   evidence-backed) but **still open for remediation** — add to the risk
   register as a confirmed (not hypothesized) execution-layer defect.
2. Before trusting any *future* extended demo run as clean evidence
   (`PHASE-5B5`'s own condition), confirm whether this specific defect has
   been fixed — it hasn't been, as of this document.
3. Check the live VPS `data/execution/` directory to confirm the archived
   test-pollution data's 58-record match is the same actual incident, not
   just a plausible coincidence of the same failure mode.
