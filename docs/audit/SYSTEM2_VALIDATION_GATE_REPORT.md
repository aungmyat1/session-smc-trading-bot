---
Date: 2026-07-12
Author: Lead Architect / Quant (Claude)
Authority: Level 8 — informational evidence. Does not supersede `docs/00_Project/DOC_AUTHORITY.md`.
Scope: Phase 5 of the System2 Completion Mission. Verification and evidence
only — per the mission's explicit "Do NOT change gate values. Only
consolidate," no gate values were changed.
---

# System 2 Validation Gate Report

## Executive Summary

Three mutually-inconsistent validation-gate definitions exist in this
repository, and none of them match CLAUDE.md's current documented gate
(n>200, PF>1.25 at standard AND 2× stress, Sharpe>1.2, MaxDD<15%, effective
2026-07-01). This confirms and extends the finding already on record in
`docs/audit/DOCUMENTATION_ALIGNMENT_REPORT.md` and
`docs/audit/STA2_REVALIDATION_PLAN.md` (prior sprint). **No gate values were
changed in this phase** — one candidate consolidation fix was attempted,
found to require more verification than this phase's scope allows, and
reverted before commit. This report documents the evidence and the exact
recommended next action instead.

## Current State — three divergent gate definitions found

| Location | `minimum_trade_count` | `minimum_profit_factor` | `maximum_drawdown` | Sharpe | Reads from config? |
|---|---|---|---|---|---|
| `config/validation.yaml` (the canonical file — has a dedicated resolver, `shared/configuration/validation.py`) | 50 | 1.0 | 10.0 | not present | — (this is the file) |
| `research/validation/engine.py`'s `ValidationConfig` dataclass defaults | **100** | 1.0 | 10.0 | not present | Only as a fallback if a YAML key is absent |
| `scripts/backtest_session_liquidity.py`'s `PHASE0_MIN_TRADES`/`PHASE0_MIN_PF` module constants | **100** | 1.0 | — | not present | **No — hardcoded, bypasses `config/validation.yaml` entirely** |
| CLAUDE.md §0.3/§0.6 (current, documented, effective 2026-07-01) | **>200** | **>1.25** (both stress levels) | **<15%** | **>1.2** | N/A — policy document |

None of the three code-level definitions reflect the current gate. All three
still reflect the pre-2026-07-01 threshold, and none compute or check
Sharpe at all.

## Evidence

- `config/validation.yaml` — read directly, confirmed `minimum_trade_count: 50`.
- `research/validation/engine.py:180-187` — `ValidationConfig` dataclass
  default `minimum_trade_count: int = 100`, a **different number** than the
  YAML file's own value (50). This default is only used when
  `load_validation_config()` can't find the key in the YAML — since the key
  is always present in the checked-in file, this specific divergence is
  latent, not currently observed in production, but is a real inconsistency
  in the fallback path.
- `scripts/backtest_session_liquidity.py:61-62` — `PHASE0_MIN_TRADES = 100`,
  `PHASE0_MIN_PF = 1.0` as module-level constants, used directly throughout
  that script (lines 306, 383-384, 467, 477-482, 752-754) with **no
  reference to `config/validation.yaml` or `shared.configuration.validation`
  anywhere in the file** — confirmed by grep. This is genuine, functional
  duplication: the ST-A2 backtest script and the SVOS validation gate can
  disagree about what "passes" for the same evidence.

### A consolidation fix was attempted and reverted — here's exactly what happened

To test whether the `research/validation/engine.py` dataclass default was
safe to align with the YAML's value (a change that would touch zero YAML
content and, if the default were truly dead code, zero observed behavior),
it was changed from `100` to `50` and the relevant test suites were run.
**7 tests in `tests/svos/test_pipeline.py` failed** with that change in
place. The change was reverted immediately, and — importantly — **the same
7 tests were re-run against the fully reverted file and failed identically**,
proving they are **pre-existing failures on `main`, unrelated to this
change** (they match a gap already documented in PR #24's own test plan:
"ROBUSTNESS/VIRTUAL_DEMO fail gracefully without external research module").
So the specific default-alignment edit tested here was not actually the
cause of any regression — but the fact that changing this default required
a real test run to determine safety (rather than being obviously inert, as
first assumed) is itself the evidence that this default is **not safely
knowable as dead code without deeper investigation than this phase's scope**,
and per the mission's explicit "do NOT change gate values," it was left
unchanged rather than merged on the strength of an after-the-fact
justification.

## Risk

- The `scripts/backtest_session_liquidity.py` duplication is the more
  consequential one: it means the ST-A2 backtest's own internal pass/fail
  reporting (`PHASE0_MIN_TRADES`/`PHASE0_MIN_PF`) is structurally
  disconnected from `config/validation.yaml`, so fixing the YAML alone (as
  `STA2_REVALIDATION_PLAN.md` task 3 already recommends) would **not**
  actually change what the backtest script itself reports as PASS/FAIL —
  both the YAML and the script would need to change together, and the
  script would need code changes (not just a config edit) to read from the
  canonical source at all.
- None of the three definitions include a Sharpe threshold in any form —
  this is a gap in the tooling, not just the values, and isn't fixable by
  "consolidation" alone; it requires the metric to be computed at all
  (already tracked in `STA2_REVALIDATION_PLAN.md` task 3: "Add Sharpe to
  `compute_metrics()`").

## Recommendation

Two separate, deliberate follow-up actions — **not performed in this
phase**, per the mission's explicit rule:

1. **Consolidation** (mechanical, lower risk): make
   `scripts/backtest_session_liquidity.py` import its thresholds from
   `shared.configuration.validation.load_validation_config()` instead of
   hardcoding `PHASE0_MIN_TRADES`/`PHASE0_MIN_PF`. This removes the true
   duplication. **Caveat**: since the script's current hardcoded value (100)
   differs from the YAML's current value (50), this consolidation would
   itself change the script's effective threshold from 100 to 50 the moment
   it's wired up — that emergent value change needs its own explicit
   sign-off, separate from the mechanical "read from one place" refactor.
2. **Gate-value update** (policy, needs owner sign-off): update
   `config/validation.yaml` to the current CLAUDE.md gate (n>200, PF>1.25
   both stress levels, Sharpe>1.2, MaxDD<15%) — already recommended in
   `STA2_REVALIDATION_PLAN.md` task 3 from the prior sprint, intentionally
   not duplicated as new work here.

## Priority

Medium — blocks trustworthy automated gate evaluation, but the ST-A2
revalidation trial (Phase 6) can proceed by comparing its results against
the CLAUDE.md gate manually/directly, without waiting for the config
consolidation.

## Estimated effort

- Consolidating `scripts/backtest_session_liquidity.py` to read from
  `config/validation.yaml`: 2-3 hours (code change + tests + explicit
  owner sign-off on the resulting threshold change).
- Updating `config/validation.yaml`'s values to the current gate: <1 hour,
  but is a policy action, not an engineering one.

## Rollback

N/A for this phase — no code or config changed. The attempted-then-reverted
edit to `research/validation/engine.py` left zero diff (confirmed via
`git diff`/`git status` after revert).

## Dependencies

None for this report. The two recommended follow-ups (above) are
independent of every other phase in this mission.

## Acceptance criteria

- [x] `config/validation.yaml` compared against project documentation (CLAUDE.md) and found not to match
- [x] Every consumer of validation constants identified (3 found, not 1)
- [x] Duplication documented precisely, with line-number evidence
- [x] Gate values NOT changed — verified via `git diff` showing zero change
- [x] A candidate fix was tested (not just assumed safe), found to need more
      verification than this phase's scope, and correctly reverted rather
      than merged on unverified reasoning
