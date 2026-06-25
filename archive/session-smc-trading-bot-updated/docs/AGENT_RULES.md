# AGENT_RULES.md
# Session Trading Bot — Agent Standing Instructions
# v1.0 — Read this before every task

---

## Project Name

Session Trading Bot

---

## §1 — HARD RULES (violation = stop and ask)

1. **Python 3.12.** No external dependencies beyond requirements.txt.
2. **UTC internally.** All timestamps stored and computed in UTC. Convert to EST only for session classification via `zoneinfo`.
3. **Bar-close execution only.** Entry price = close of signal candle. Never use open of next bar.
4. **No lookahead bias.** When processing bar `i`, only `candles[:i]` may be read. No future candles, no repainting logic.
5. **One feature per task.** If a task grows beyond its defined scope, stop and raise it.
6. **One commit per task.** Commit only when the task is complete and tests pass.
7. **Never modify the execution layer** (`execution/`) unless the task explicitly targets it.
8. **Never modify the risk layer** (`execution/risk_manager.py`) unless the task explicitly targets it.
9. **Always create or update tests** for every module touched.
10. **Always update `docs/PROJECT_STATUS.md`** at end of task — mark completed items `[x]`.
11. **Always recommend the next task** at end of output.
12. **Read only required files.** Do not load the full codebase speculatively.
13. **Maximum 5 files per task** unless the task spec says otherwise.

---

## §2 — STRATEGY ISOLATION

- Strategy A (Session Liquidity) lives in `strategy/session_liquidity/`.
- Strategy B (SMC) lives in `session_smc/` (renamed to `strategy/smc/` when promoted).
- **Never mix logic** between Strategy A and Strategy B.
- The execution layer calls `signal.side / signal.entry / signal.stop_loss / signal.take_profit / signal.reason / signal.session / signal.timestamp` — nothing else.
- The `Signal` dataclass in `strategy/session_liquidity/entry_engine.py` is the contract between strategy and execution.

---

## §3 — CONTEXT FILES (read in this order)

1. `docs/AGENT_RULES.md` — you are here
2. `docs/PROJECT_STATUS.md` — current milestone and task
3. The spec file for the current task's strategy:
   - Strategy A → `docs/STRATEGY_A_SESSION.md`
   - Strategy B → `docs/STRATEGY_B_SMC.md`
4. Task-specific source files only

---

## §4 — OUTPUT FORMAT

Every response must include:

```
## Summary
One sentence.

## Files Modified
- path/to/file.py (+N lines)

## Tests Added
- tests/session_liquidity/test_X.py  (N tests)

## Risks
- Any lookahead, edge case, or known limitation

## Next Task
[task-id] — one sentence description
```

---

## §5 — BACKTEST GATE (non-negotiable)

- Trades ≥ 100 AND Profit Factor > 1.0 at **standard** spread
- AND Profit Factor > 1.0 at **2× spread** stress test
- Per `docs/BACKTEST_SPEC.md`
- No demo deployment until gate passes.
- No execution-layer integration until gate passes.

---

## §6 — LIVE TRADING GATE

`LIVE_TRADING = False` in `.env` until owner manually changes it.
Agent must never set `LIVE_TRADING = True`.
