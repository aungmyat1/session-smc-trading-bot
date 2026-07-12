---
Date: 2026-07-12
Status: Authoritative
Version: 1.0
Updated: 2026-07-12
Owner: Lead Architect
Authority: Level 1 — Product Milestone Truth
Supersedes: (none — first governed version; previously unheadered/Draft by
  DOC_AUTHORITY.md's default rule)
Related: 00_Project/DOC_AUTHORITY.md, 00_Project/TWO_SYSTEM_ARCHITECTURE_TRUTH.md
---

# Project Objective

The current milestone is **Project Readiness v1**, an evidence-backed demo trading system. It does not authorize live trading.

The required chain of custody is:

```text
strategy specification → historical evidence → validation → signed approval package → demo execution → operational report
```

Success means the strategy engineering platform produces repeatable evidence, the bot executes only a valid approved package, and demo operation remains stable without manual repair. Profit optimization and live-capital activation are outside this milestone.

BTCUSDT is included in the Strategy Engineering Platform for offline research, validation, replay, backtesting, analytics, and virtual demo. It is not enabled in the Simple Trading Bot execution allowlist and does not authorize exchange connectivity or live trading.
