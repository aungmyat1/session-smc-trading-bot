# PHASE 4 — ACCOUNT ISOLATION AUDIT
# Session SMC Trading Bot (Updated) vs Production Bot
**Date:** 2026-06-25

---

## 1. METAAPI ACCOUNT ID ANALYSIS

### Current state (from .env)
```
METAAPI_ACCOUNT_ID      = d6f6eec3-96d5-4001-a802-62b3f4b49817  ← Production bot
VANTAGE_DEMO_METAAPI_ID = d6f6eec3-96d5-4001-a802-62b3f4b49817  ← Same UUID!
```

**Finding:** Both env vars point to the same MT5 account. There is currently ONE demo
account shared between both bots.

### Account usage by entry point

| Entry Point | Env Var Used | Account |
|-------------|-------------|---------|
| `session-smc-trading-bot/bot.py` | `METAAPI_ACCOUNT_ID` | d6f6eec3… |
| `session-smc-trading-bot-updated/bot.py` line 72 | `METAAPI_ACCOUNT_ID` | d6f6eec3… (same) |
| `session-smc-trading-bot-updated/execution/mt5_connector.py` mode=demo | `VANTAGE_DEMO_METAAPI_ID` | d6f6eec3… (same) |

**Current isolation status: NONE — both bots use the same account**

### Required fix for true isolation

Two options:

**Option A (Recommended) — Separate MT5 demo accounts:**
1. Open a second Vantage MT5 Demo account
2. Register it in MetaAPI → get new UUID
3. Set updated bot's `.env`: `VANTAGE_DEMO_METAAPI_ID=<new-uuid>`
4. Change updated bot's `bot.py` line 72:
   ```python
   # Before:
   METAAPI_ACCOUNT_ID: str = os.getenv("METAAPI_ACCOUNT_ID", "")
   # After:
   METAAPI_ACCOUNT_ID: str = os.getenv("VANTAGE_DEMO_METAAPI_ID", "")
   ```

**Option B (Acceptable) — Same account, magic number isolation:**
- Both bots use same account
- Production bot: magic numbers 21001, 21002
- Updated bot: magic number 21099
- Each bot's order manager filters by its own magic numbers
- Risk: shared account balance, shared position count at broker level
- Acceptable for demo phase where total exposure is small

**Current deployment:** Option B is in effect (same account, different magic numbers).
Option A should be implemented before running both simultaneously.

---

## 2. MAGIC NUMBER REGISTRY

| Bot | File | Symbol | Magic Number | Unique? |
|-----|------|--------|-------------|---------|
| Production | config/config.json | EURUSD | 21001 | ✅ |
| Production | config/config.json | GBPUSD | 21002 | ✅ |
| Updated | config/demo.yaml | Portfolio demo | 21099 | ✅ Isolated |
| Updated | config/config.json | EURUSD | 21001 | ⚠️ Conflicts with production if shared account |
| Updated | config/config.json | GBPUSD | 21002 | ⚠️ Conflicts with production if shared account |

**Verdict:** If updated bot runs with `demo.yaml` (magic 21099), positions are isolated.
If it falls back to `config.json` magic numbers, isolation breaks.

**Recommendation:** Updated bot's VantageDemoExecutor uses `magic: int = 21001` (default param).
Change the default to 21099 to match demo.yaml — OR — always pass magic explicitly from demo.yaml.

---

## 3. LOG FILE CONFLICT ANALYSIS

### Production bot log paths (relative to production bot CWD)
```
logs/bot.log
logs/portfolio_demo_trades.jsonl
logs/shadow_trades.jsonl        ← SHARED NAME RISK
logs/portfolio_runner.log       ← SHARED NAME RISK
```

### Updated bot log paths (from demo.yaml)
```
logs/st_a2_demo_trades.jsonl    ✅ Unique
logs/shadow_trades.jsonl        ⚠️ Same filename as production
logs/st_a2_runner.log           ✅ Unique
logs/st_a2_demo.log             ✅ Unique
```

**Conflict:** `logs/shadow_trades.jsonl` name is shared.

**BUT:** Both bots run from different working directories:
- Production: `/home/aungp/session-smc-trading-bot/logs/shadow_trades.jsonl`
- Updated: `/home/aungp/session-smc-trading-bot/session-smc-trading-bot-updated/logs/shadow_trades.jsonl`

**Absolute paths are different — no actual file conflict when run from their own directories.**

---

## 4. DATABASE CONFLICT ANALYSIS

| Bot | DB Path (relative to CWD) | Absolute Path |
|-----|--------------------------|---------------|
| Production | `data/trade_journal.db` | `/home/aungp/session-smc-trading-bot/data/trade_journal.db` |
| Updated | `data/trade_journal.db` | `/home/aungp/session-smc-trading-bot/session-smc-trading-bot-updated/data/trade_journal.db` |

**Different absolute paths — no DB conflict when each bot runs from its own directory.**

Note: Updated bot's `data/` was created as a fresh copy during Phase 5 fix. The symlinked
`data/historical/` is read-only (CSV files). The `data/trade_journal.db` is NOT symlinked
and will be created separately in the updated bot's own data dir.

---

## 5. RISK ISOLATION SUMMARY

| Risk | Status | Mitigation |
|------|--------|-----------|
| Same MT5 account | ⚠️ CURRENT STATE | Option A: separate accounts (recommended) |
| Same magic numbers (21001/21002) | ⚠️ IF config.json used | Use demo.yaml (magic 21099) |
| Log file collision | ✅ SAFE | Absolute paths are different |
| DB collision | ✅ SAFE | Absolute paths are different |
| Position count confusion | ⚠️ IF same account | Broker sees all positions; each bot filters by magic |
| Balance drawdown overlap | ⚠️ IF same account | Two bots can both hit daily loss limits simultaneously |

---

## VERDICT

| Check | Result | Note |
|-------|--------|------|
| Account separation | ⚠️ PARTIAL | Same account currently — magic isolation only |
| Magic number isolation | ✅ PASS (with demo.yaml) | 21099 is unique |
| Log file isolation | ✅ PASS | Different CWDs = different absolute paths |
| Database isolation | ✅ PASS | Different CWDs = different absolute paths |
| bot.py account fix needed | ⚠️ PENDING | Line 72: use VANTAGE_DEMO_METAAPI_ID |

**Required before running both bots simultaneously:**
1. Either open a second Vantage MT5 demo account (Option A), OR
2. Accept shared account with magic isolation (Option B — acceptable for demo only)
3. Fix bot.py line 72 to read `VANTAGE_DEMO_METAAPI_ID` not `METAAPI_ACCOUNT_ID`
