# DEMO_GATE_DECISION.md
# Demo-Trading Activation Gate — Final Decision Record
# Status: TEMPLATE — populate after E1–E4 execution gate completes
# Prerequisite: E6 cost revalidation PASS AND OPS-01 stability run complete

---

## Prerequisites Summary

<!-- Verify before populating this document -->

| Prerequisite | Requirement | Status |
|---|---|---|
| OPS-01 7-day stability run | Complete by 2026-06-28, 0 critical events | |
| E5 spread capture | ≥5 London + ≥5 NY sessions + ≥7,000 rows | |
| E6 cost revalidation | PF_2x ≥ 1.00 at measured Vantage costs | |
| E1 7-day execution gate | 7 consecutive days, LIVE_TRADING=true, 0 crashes | |
| E2 signal validation | ≥1 SIGNAL_CREATED with correct fields | |
| E3 order lifecycle | ≥1 complete lifecycle (fill or valid reject) | |
| E4 manual restart test | Restart clean, state intact, no spurious orders | |

---

## E1 — 7-Day Runtime Results

<!-- Populate after E1 window completes -->

| Day | Date | Health check | Gaps >600s | Events |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | E4 restart test | | |
| 4 | | | | |
| 5 | | | | |
| 6 | | | | |
| 7 | | | | |

**E1 pass: 7/7 days clean** — [ ] PASS / [ ] FAIL

---

## E2 — Signal Validation

<!-- Populate after first signal observed -->

| Field | Value |
|---|---|
| Date of first signal | |
| Symbol | |
| Session | |
| Side | |
| sl_pips | |
| tp_r | |
| Fields complete | |

**E2 pass: ≥1 signal with correct fields** — [ ] PASS / [ ] FAIL

---

## E3 — Order Lifecycle

<!-- Populate after first lifecycle observed -->

| Event | Timestamp | Symbol | Detail |
|---|---|---|---|
| SIGNAL_CREATED | | | |
| ORDER_SUBMITTED | | | |
| ORDER_FILLED or ORDER_REJECTED | | | |
| POSITION_CLOSED (if filled) | | | |

SL placed on fill: [ ] Yes / [ ] N/A (rejection)
TP placed on fill: [ ] Yes / [ ] N/A (rejection)
Session-end close correct: [ ] Yes / [ ] N/A

**E3 pass: one full lifecycle observed** — [ ] PASS / [ ] FAIL

---

## E4 — Manual Restart Test

<!-- Populate after deliberate restart on Day 2–3 -->

| Check | Result |
|---|---|
| Restart date/time | |
| Reconnect time | s |
| Spurious orders after restart | |
| bot_state.json unchanged | |
| LIVE_TRADING guard restored from .env | |

**E4 pass: restart clean** — [ ] PASS / [ ] FAIL

---

## Gate Checklist

<!-- Complete all items before writing the verdict below -->

| Gate | Status |
|---|---|
| E1 — 7-day runtime | [ ] PASS / [ ] FAIL |
| E2 — Signal validated | [ ] PASS / [ ] FAIL |
| E3 — Order lifecycle | [ ] PASS / [ ] FAIL |
| E4 — Restart test | [ ] PASS / [ ] FAIL |
| E5+E6 — Cost confirmed | [ ] PASS / [ ] FAIL |
| OPS-01 — Stability | [ ] PASS / [ ] FAIL |

---

## Demo Gate Verdict

<!-- Populate after all gates checked -->

**Verdict:** <!-- PENDING -->

If all gates PASS:

> STATUS: DEMO GATE PASSED
> ST-A2 is confirmed for execution on measured costs.
> Proceed to micro-live evaluation at the owner-approved parameters:
> - Account: $1,000 Vantage live
> - Risk per trade: 0.25%
> - Max positions: 1
> - Validation period: first 20 trades

If any gate FAIL:

> STATUS: DEMO GATE BLOCKED — [list failed gates]
> Do not proceed to micro-live.
> See rollback procedure in docs/OPS02_ACTIVATION_CHECKLIST.md Section 4.

---

## Micro-Live Parameters (post-gate, owner-approved 2026-06-24)

| Parameter | Value |
|---|---|
| Account | $1,000 Vantage live |
| Risk per trade | 0.25% |
| Max open positions | 1 |
| First 20 trades | Treated as validation period |
| Size increase | Only after live results consistent with ST-A2 expectations |
| Kill switch | 10% DD ($100) |

---

## LIVE_TRADING Authorization

The agent does not change LIVE_TRADING. All activation steps are owner-manual.
Reference: `docs/OPS02_ACTIVATION_CHECKLIST.md` Section 2.

---

*DEMO_GATE_DECISION.md | Template | Populate after E1–E4 gate (~2 weeks from 2026-06-30)*
