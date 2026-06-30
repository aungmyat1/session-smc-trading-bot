# Quality Report ✅

**Status:** `PASS`
**Quality:** 100.0  |  **Security:** 96.0  |  **Architecture:** 100.0  |  **Documentation:** 59.7
**Generated:** 2026-06-30T07:01:26.595155+00:00  |  **Duration:** 19.13s

## Stage Summary

| Stage | Status | Score |
|-------|--------|------:|
| code_quality | ✅ PASS | 100.0 |
| security | ✅ PASS | 96.0 |
| architecture | ✅ PASS | 100.0 |
| dependency | ✅ PASS | 100.0 |
| documentation | ✅ PASS | 59.7 |

### code_quality
- ⚠️ isort: 0 file(s) have unsorted imports

### security
- ⚠️ bandit output unparseable: Working... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:02
{
  "errors": [],
  "generated_at": "2026-06-30T07:01:20Z",
  "metrics": {
    "/home/aungp/session-smc-trading-bot/agents/__init__.py"

### documentation
- ⚠️ Missing docstring: svos/application/backtest.py:45 def passed()
- ⚠️ Missing docstring: svos/application/backtest.py:48 def to_dict()
- ⚠️ Missing docstring: svos/application/backtest.py:57 def __init__()
- ⚠️ Missing docstring: svos/application/backtest.py:144 def _evaluate_gate()
- ⚠️ Missing docstring: svos/application/backtest.py:200 def _default_cost_model()
- ⚠️ Missing docstring: svos/application/backtest.py:209 def _drive_lifecycle()
- ⚠️ Missing docstring: svos/application/robustness.py:43 def passed()
- ⚠️ Missing docstring: svos/application/robustness.py:46 def to_dict()
- ⚠️ Missing docstring: svos/application/robustness.py:55 def __init__()
- ⚠️ Missing docstring: svos/application/robustness.py:159 def _normalize_trades()
