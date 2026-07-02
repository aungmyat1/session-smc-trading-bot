# Live dashboard backend audit

**Dashboard audited:** `http://34.87.36.159:8090/dashboard/`  
**Audit time:** 2026-07-01 17:45–17:46 UTC  
**Scope:** the deployed FastAPI status dashboard, not the separate Flask `/live-dashboard/` UI.

## Executive verdict

The dashboard is a **demo-account status view backed by local files**. It does not query Vantage or MetaAPI when a browser requests the page. The runner queries the broker, writes local JSON/JSONL caches, and the dashboard reads those caches. Consequently, “live” means “the page was regenerated,” not “the displayed values were just confirmed with the broker.”

At audit time the account, position, and candle caches were fresh (roughly one runner cycle), and their values were internally consistent with `/api/status`. They are credible projections of the Vantage demo account, but no widget proves broker freshness, cache age, successful reconciliation, or execution-engine agreement. The system log was demonstrably stale by about **10 hours 24 minutes** because the dashboard selects an old log file before the active one.

The deployed server exactly matches the older `96568ea` dashboard shape. It is behind the checked-out backend: `/api/control/state`, `/api/control/permission`, `/api/health/summary`, `/api/readiness/report`, and `/metrics` all returned HTTP 404, and `/api/status` omitted the newer emergency-stop and journal fields.

Observed live state:

- Demo account: balance/equity/free margin `$996.01`; no margin and no open positions.
- Runner cache: `running`, broker cache: `connected`, last tick `17:45:26 UTC`, state written `17:45:36 UTC`, 60-second runner interval.
- `/api/status` values did not change across samples three seconds apart; only its response timestamp changed.
- Candle caches ended at `17:45:00 UTC`: EURUSD `1.13797`, GBPUSD `1.32784`, XAUUSD `4070.75`.
- Active runner log (`logs/strategy_demo.log`) was written at `17:45:35 UTC`; the dashboard showed `logs/smc_ob_fvg_demo.log` ending at `07:21:16 UTC`.
- Runtime mode was `demo` with `DEMO_ONLY=true` and `live_trading=false`. This is real demo-broker market/account data, not a live-money account.

## Data path

`Vantage MT5 demo → MetaAPI → scripts/run_st_a2_demo.py → local cache files → dashboard/status_server.py → server-rendered HTML`

The browser refreshes `GET /dashboard/` every 30 seconds with `cache: no-store`. The runner normally refreshes its broker-derived cache every 60 seconds, so normal displayed age is approximately 0–90 seconds. There is no WebSocket/SSE feed and no explicit HTTP cache headers. A fresh HTML response can contain arbitrarily old file data.

## Widget mapping

There is no database query for most deployed widgets. “None (file cache)” below is intentional.

| Dashboard widget | Frontend component | API | Database / query | Service | Source of truth | Refresh | Accuracy, problems, recommendations |
|---|---|---|---|---|---|---|---|
| Header: DEMO/LIVE, pairs, RUNNING, timestamp, strategy, render time | Server-rendered `section-header`; 30-second DOM replacement script | `GET /dashboard/`; subset also in `GET /api/status` | None; `logs/strategy_demo_state.json` | FastAPI `dashboard.status_server._build_html`; runner state writer | Mode/config: runner state. Process truth should be systemd/process health plus heartbeat age | Browser 30s; state about 60s | **Mixed.** DEMO was correct. RUNNING only tests cached `state.status == running`; it does not check PID, systemd, broker connection, or tick age. “● live” only means the last HTML fetch succeeded. Add `last_tick_age`, broker status, deployment revision and a stale/offline state; verify PID/service health. |
| Vantage Demo Account | `section-account` card | `GET /dashboard/`; account object in `GET /api/status` | None; `state.account` in `logs/strategy_demo_state.json` | `VantageDemoExecutor.get_account_info()` through the runner; page only reads cache | MetaAPI/Vantage account information | Browser 30s; broker snapshot about 60s | **Real demo-broker snapshot, cached.** Not simulated at audit time, but not fetched by the dashboard. Float P&L is derived as equity minus balance. No `as_of`, cache-age, or broker-connected warning. Expose broker timestamp/account ID suffix and reject or mark snapshots stale after 2 runner intervals. |
| Session Status | `section-session` card | `GET /dashboard/`; session in `GET /api/status` | None; state JSON | Runner `_session_gate()` and decision state | Execution runner clock/state | Browser 30s; runner about 60s | **Derived, cached.** Session and last decision match runner projection. Fixed London/NY labels are static. Last tick is shown but not aged or validated. Show age, status fields, and stale threshold; use the execution engine's configured session windows instead of duplicated display constants. |
| Last Signal | `section-signal` card | `GET /dashboard/`; `last_signal` in `GET /api/status` | None; state JSON. SQLite `trades` exists but is not queried by deployed UI | Runner signal/router/risk/execution pipeline | Execution record plus broker order/fill record | Browser 30s; event-driven only when runner writes state | **Real engine candidate, cached, but ambiguous.** It can represent a shadow/simulated, blocked, failed, or placed signal; the card does not show `simulated`, execution status, broker order ID, or reconciliation. At audit it correctly showed no signal. Back it with immutable execution records and display lifecycle state and broker ID. |
| Open Positions | Conditional `section-positions` table | `GET /dashboard/`; `open_positions` in `GET /api/status` | None; state JSON | `TradeManager.get_positions()` → demo execution adapter → MetaAPI | Broker open-position list, reconciled with execution state | Browser 30s; normally about 60s | **Broker-derived cache.** At audit both page and API showed none. On some fetch exceptions the runner writes `[]`, making “broker read failed” indistinguishable from “zero positions”; elsewhere it may retain the old list. This is unsafe. Store fetch status/time, never convert an error to an authoritative empty list, and reconcile broker positions against execution records. |
| Live M15 Charts (EURUSD, GBPUSD, XAUUSD) | `section-charts`, tab buttons, server-generated SVG | `GET /dashboard/`; `/api/status` exposes only derived price/stage/bias/signal | None; `logs/candles/{SYMBOL}_M15.json` (200 rows), chart uses last 60 | Runner `MT5Connector.get_candles`; dashboard `_load_candles`, `_analyze`, `_render_chart_svg` | Broker M15 candles for OHLC; execution strategy for signal truth | Browser 30s; files about 60s; bars are M15 | **Real demo-broker candles, cached.** Last closes matched `/api/status`. Zones/stages are recomputed in the dashboard, not read from execution-engine decisions. No last-bar age, completeness flag, bid/ask distinction, or fetch-error status. Add candle `as_of`, closed/forming-bar marker, source, gap checks, and consume engine-produced analysis rather than recomputing it. |
| EURUSD pipeline card | `_pair_card('EURUSD')` | `GET /dashboard/`; summary in `GET /api/status` | None; EURUSD candle JSON | Dashboard `_analyze` using `smartmoneyconcepts` | Currently dashboard calculation; should be engine strategy snapshot | Browser 30s; candle cache about 60s | At audit: stage 1, bearish, FLAT, `1.13797`. **Derived, not execution authority.** Dashboard and adapter duplicate logic and differ in ordering/constraints: the engine gates session and spread first and uses configurable `min_bars`; dashboard uses hard-coded 60 bars, 5-pip buffer, 1×ATR and kill-zone times. Publish the engine's gate-by-gate decision. |
| GBPUSD pipeline card | `_pair_card('GBPUSD')` | Same as EURUSD | None; GBPUSD candle JSON | Same as EURUSD | Same as EURUSD | Same | At audit: stage 1, bearish, FLAT, `1.32784`. Same divergence and staleness risks. |
| XAUUSD pipeline card | `_pair_card('XAUUSD')` | Same as EURUSD | None; XAUUSD candle JSON | Same as EURUSD | Same as EURUSD | Same | At audit: stage 3, bullish, FLAT, `4070.75`. The dashboard's hard-coded five-**pip** buffer is especially misleading for XAU because `_PIP[XAUUSD]=0.1`, producing a 0.5 price buffer. Same engine-divergence risks. |
| Strategy Guide: entry rules | Static `_strategy_section` HTML | `GET /dashboard/` | None | Dashboard renderer | Documentation/config, not runtime state | Re-rendered 30s; content changes only on deploy | **Mostly static documentation, not a live widget.** It may drift from code. Generate rules from versioned strategy metadata and show strategy commit/config hash. |
| Strategy Guide: Live Parameters | `_strategy_section`, `_STRAT_CFG` imported at dashboard startup | `GET /dashboard/` | None | Strategy adapter `DEFAULT_CONFIG` imported into dashboard process | Effective runner configuration | Re-rendered 30s, but module config is fixed until dashboard restart | **Potentially inaccurate.** It shows adapter defaults, not necessarily runtime overrides, environment spread limits, or deployed runner config. “Pairs” and “Timeframe” are hard-coded. Expose the effective runner config snapshot and its load time. |
| Strategy Guide: exit rules | Static `_strategy_section` HTML plus some default config values | `GET /dashboard/` | None | Dashboard renderer | Effective execution/risk policy | Re-rendered 30s; static until deploy/restart | **Documentation only.** It omits router, circuit breaker, portfolio, permission, broker fill, and emergency controls. Link each claim to effective policy values and flag any override. |
| Kill Zone Timeline | `_kill_zone_svg(now)` | `GET /dashboard/` | None | Dashboard server UTC clock | Server UTC time plus effective session configuration | Browser 30s | Current-time needle is real server time; zone windows are hard-coded. It does not use broker time or prove the runner's session gate. Render from effective strategy config. |
| Example Setup diagram | `_example_setup_svg()` | `GET /dashboard/` | None; literal candle coordinates in Python | Dashboard renderer | None; illustrative fixture | Static | **Simulated illustration.** It is not market data and should be labelled “illustrative / synthetic” prominently. |
| Recent Trades | `section-trades` table | `GET /dashboard/`; absent from `/api/status` | No DB. Reads last 25 qualifying lines from `logs/trades.jsonl` | Generic `execution.trade_logger.TradeLogger`, not the current demo runner journal | Broker execution/fill history reconciled with journal DB | Browser 30s; file only when its unrelated producer writes | **Stale/wrong source for this runner.** File mtime was 2026-06-26, while the active runner writes `logs/strategy_demo_trades.jsonl` and `data/trade_journal.db`. The title says “Recent Trades,” but rows may include signals, submissions, rejections, and historical events. Query the reconciled SQLite/execution store and label event type/status/source. |
| System Log — last 30 lines | `section-log`, server-rendered lines | `GET /dashboard/` | None; first existing file from `smc_ob_fvg_demo.log`, then `strategy_demo.log` | Python logging | Active runner/service logs | Browser 30s; underlying active log continuously | **Demonstrably stale.** Loader always prefers the old `smc_ob_fvg_demo.log`; displayed last line was 07:21:16 while active `strategy_demo.log` was current at 17:45:35. Select by configured service or newest mtime, show filename and last-write age, or use journald/central logging. Escape log text before embedding HTML. |
| Refresh indicator/countdown/button | Inline JavaScript in HTML | Fetches only `GET /dashboard/` with `cache: no-store` | None | Browser | Successful HTTP response, not data freshness | Countdown 1s; fetch 30s; retry 15s after failure | **Misleading.** A 200 response displaying stale caches remains green “live.” Have the backend return per-source timestamps/health and make the indicator reflect the oldest critical source. |

## API-to-storage mapping

| Deployed endpoint | Consumers | Storage/query | Notes |
|---|---|---|---|
| `GET /dashboard/` | Entire visible dashboard | Reads state JSON, three candle JSON files, `trades.jsonl`, and one log file; recomputes SMC analysis in-process | This is the actual widget data endpoint despite returning HTML. No authentication observed. |
| `GET /api/status` | External/status clients; not used by the page refresh script | Same state and candle files; recomputes SMC analysis | Response timestamp is generation time, not source time. It omits broker status, last tick, cache ages, execution state, and deployed revision. |
| `GET /` | Navigation | None | Redirects to `/dashboard/`. |

The checked-out code contains additional endpoints and SQLite analytics, but they are **not deployed** on this host and therefore are not sources for any audited widget.

## Priority recommendations

1. **Make freshness explicit and fail closed.** Return `source_updated_at`, `age_seconds`, `fetch_status`, and stale thresholds for account, positions, candles, decisions, trades, and logs. Never display a failed position fetch as zero positions.
2. **Use one execution source of truth.** Persist the runner's exact gate results, signals, orders, fills, positions, and reconciliation status; dashboard widgets should project those records rather than rerun strategy logic.
3. **Reconcile with the broker.** Periodically compare broker account/positions/orders with the execution store and surface mismatch counts and last successful reconciliation.
4. **Fix the two incorrect feeds immediately.** Read the active runner log rather than the first legacy filename, and replace `logs/trades.jsonl` with the current demo journal/reconciled SQLite execution history.
5. **Correct the “live” contract.** Green should require a fresh runner heartbeat, connected broker, successful latest reads, and acceptable reconciliation—not merely HTTP 200.
6. **Deploy and identify one revision.** Expose commit SHA/build time and bring the host up to the intended status-server version; add a deployment smoke test for required endpoints.
7. **Separate real, derived, and illustrative data visually.** Mark the environment “Vantage DEMO,” label cached timestamps, call pipeline values “dashboard-derived” until unified, and label the example SVG synthetic.
8. **Add operational safety.** Authenticate the dashboard, escape all state/log values rendered into HTML, add cache-control headers, and expose health/readiness/metrics only from the deployed revision after access controls are set.

## Overall accuracy assessment

| Dimension | Verdict |
|---|---|
| Real vs simulated | Market/account data is from a real Vantage **demo** broker connection; the example diagram is synthetic; execution may still be simulated because `DEMO_ONLY=true`. |
| Live broker data | Indirect only. The runner queries MetaAPI; the dashboard never does. |
| Cached | Yes—nearly every dynamic widget is file-backed. |
| Stale | Account/candles were fresh during the sample; trades were at least several days old and system log about 10h24m old. No widget enforces freshness. |
| Matches execution engine | Account/positions/last signal are runner projections. Pipeline cards/charts are independently recomputed and are not authoritative engine state. Recent Trades uses the wrong journal. |
| Safe as an operational control plane | **No.** Suitable as a demo observability aid after prominent freshness caveats; not reliable enough for live-money decisions. |
