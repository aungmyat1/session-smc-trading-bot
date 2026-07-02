# Project Overview

---
Owner: Product / Architecture
Status: Draft
Version: 0.1
Last Reviewed: TODO
Next Review: TODO
Related Documents: docs/SYSTEM_ARCHITECTURE.md, docs/svos/CORE_ARCHITECTURE.md
---

Mission
: TODO — concise mission statement to be verified and approved.

Business Objective
: TODO — summarize business goals.

Technical Objective
: TODO — summarize technical goals (SVOS research boundary, production execution boundary).

Current Maturity
: TODO — state current maturity and key dates (use docs/svos/PROJECT_STATUS_REPORT_2026-06-29.md)

Current Architecture (summary)
- Two-system separation: SVOS (research + validation) and Production Execution (Vantage bot).
- See `docs/architecture/system_architecture.md` for canonical diagrams.

System Boundaries
- SVOS: research, validation, offline virtual demos (no broker connections)
- Production: simple Vantage Forex Bot that executes approved strategy packages (broker credentials stored separately)

Non-goals
- SVOS does not execute live trading.

Owner: TODO
Last reviewed: TODO
Status: Draft
