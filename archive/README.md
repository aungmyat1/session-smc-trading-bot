# archive/

Holds superseded or completed-phase code. Nothing here is production-active.
30-day hold before permanent deletion (per REPOSITORY_AUDIT.md §4).

## Contents

### session-smc-trading-bot-updated/
Stale snapshot of the project root from ~2026-06-18 (before Dukascopy pipeline,
D2 modules, replay_db.py, build_research_db.py were added).
Root is ~6 months newer on all production modules.
Contains unique docs: PHASE1-G audit series, replay_results/ — preserved here.

### Database-F-prototype/
External prototype project dropped into session_smc/Database F/.
Contains generic SMC feature generation with np.random.random() simulation.
Schema is incompatible with vmassit. Fully superseded by:
  - scripts/build_research_db.py (feature extraction)
  - scripts/replay_db.py (real ST-A2 replay)

### scripts-phase-complete/
Scripts from completed research phases:
  - E6: spread cost model (cost frozen at 1.4/1.8 pip)
  - Phase-2: spread collection (done)
  - OPS-01: MetaAPI 30-day operational run (complete)
  - EXP01-05: post-hoc filter experiments (results in research/)

### docs-phase-complete/
Documentation from completed phases (E6, OPS01).
Historical record — do not delete.

## Deletion Policy
No file in archive/ to be permanently deleted without explicit CONFIRM-DELETE token.
