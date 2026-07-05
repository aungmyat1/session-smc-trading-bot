# Session SMC Trading Bot Dashboard Upgrade Specification
## Architectural Blueprint & Technical Deliverables

This specification establishes the blueprint for upgrading the Session SMC (Smart Money Concepts) Trading Bot Dashboard from a static documentation page to an active, industrial-grade **Live Strategy Intelligence Dashboard** (Operations Control Center).

---

## 1. Dashboard Audit Report

The current repository represents a React client with placeholders, originally showing a static documentation page. 
*   **Pair Cards**: Shows static names of symbols (e.g. EURUSD, GBPUSD) but lacks live state pipeline visualization.
*   **Strategy Guide**: Collapsed by default. Outlines entry/exit rules and static parameters, but does not show what the live engine is doing *right now*.
*   **Kill Zone Timeline**: Standard SVG/HTML rendering of London (07:00-11:00) and NY (12:00-16:00) sessions. Needs a live-updated needle and background confluences.
*   **Example Trade SVG**: Illustrates a textbook 17-candle SMC bullish setup. Helpful as reference but entirely static.
*   **Trades Table**: List of past trades. Lacks execution details, MAE/MFE statistics, commission/slippage, or real RR analysis.

---

## 2. Gap Analysis

| Feature | Current State | Target State (Upgraded) | Gap |
|---|---|---|---|
| **Live State Engine** | None. Static React state. | Real-time state machine tracking HTF Bias, Liquidity, CHoCH, BOS, OB, FVG, Confluence, spread, risk, position size. | Complete backend state evaluation piped to frontend. |
| **Signal Qualification** | Paragraph list in Guide. | Live Checklist with checklists, overall signal quality % meter. | Checklist component reflecting live market criteria in real-time. |
| **Signal Rejection Logs** | Not displayed. | Stream of rejected signals with reason, timestamp, pair, and metric breached. | Rejection log database table/store and frontend panel. |
| **Market Structure Data** | Not tracked. | Live Trend, HTF Bias, Active OB/FVG zones, swing highs/lows, ATR, and live spread. | API and WebSocket payload feeding structure data. |
| **Active SMC Objects** | Static SVG drawing. | Interactive table and chart overlay showing active OBs, FVGs, and Liquidity Pools. | Real-time tracking of mitigation indexes and age/strength. |
| **Pre-Trade Decision Card** | None. | Pending trade projection: SL, TP, Risk/Reward, Expected Profit/Loss, and Lot size. | Execution confirmation window and pending-state card. |
| **Post-Trade Metrics** | Static Columns. | Deep analysis: MAE, MFE, Execution Latency, Slippage, Commission, Realized RR. | Post-trade calculator on trade exits, exposed in UI. |
| **System Observability** | None. | Real-time ping, latency, clock sync, and microservices heartbeat (Broker, Redis, DB). | Observability agent in server broadcasting health signals. |
| **Live Chart Overlay** | None. | Custom responsive chart engine displaying real-time candles overlaid with OB, FVG, and Trade vectors. | Interactive SVG/Canvas chart with technical overlay controls. |

---

## 3. Upgrade Architecture

The system utilizes an Express backend that embeds Vite during development, transitioning to compiled Node (via CJS bundle) in production.
We introduce a **Live SMC Simulator & Strategy Engine** inside the backend that runs a tick loop (every 1.5 seconds) simulating EURUSD, GBPUSD, and USDJPY. It calculates technical metrics, triggers trades, rejects invalid signals based on spread spikes or session times, and maintains full state consistency.

```
+--------------------------------------------------------------------------+
|                            EXPRESS BACKEND                               |
|                                                                          |
|  +--------------------+    +--------------------+    +----------------+  |
|  | SMC Strategy Sim   |--->| System Health Agt  |--->| REST API       |  |
|  | EURUSD / GBPUSD    |    | broker, db, redis  |    | /api/trades    |  |
|  +--------------------+    +--------------------+    | /api/status    |  |
|            |                         |               +----------------+  |
|            v                         v                                   |
|  +----------------------------------------------+                        |
|  |            WS BROADCAST ENGINE               |                        |
|  +----------------------------------------------+                        |
+--------------------------|-----------------------------------------------+
                           | (WS Port 3000 / Native Frames)
                           v
+--------------------------------------------------------------------------+
|                            VITE CLIENT                                   |
|                                                                          |
|  +------------------+   +-------------------+   +---------------------+  |
|  | App.tsx          |-->| WS Context Provider|-->| Dashboard Components|  |
|  | Core Layout      |   | state, reconnect  |   | Chart, Pipeline, etc|  |
|  +------------------+   +-------------------+   +---------------------+  |
+--------------------------------------------------------------------------+
```

---

## 4. Component Hierarchy

```
App (Layout Container)
├── Header (Dashboard stats, Clock, Global Systems Status)
├── SystemHealthGrid (Heartbeats, microservices status, latency meters)
├── Main Grid (Layout)
│   ├── Left Column
│   │   ├── PairSelector & ActiveStructure (Trend, HTF Bias, Swing Highs, Spread, ATR)
│   │   ├── LiveStrategyPipeline (Interactive chevron timeline with status flags)
│   │   └── SignalQualificationCard (Checklist, overall confidence meter, execution trigger)
│   ├── Center Column
│   │   ├── LiveChartOverlay (Candlestick renderer + OB/FVG visual overlays + Trade lines)
│   │   └── ActiveSmcObjectsPanel (Age, strength, mitigation indicators)
│   └── Right Column
│       ├── SignalRejectionPanel (Chronological stream of rejected signals)
│       ├── TradeDecisionCard (Buy/Sell, entry, SL, TP, expected PnL, trigger lot calculations)
│       └── SessionAnalytics (Win Rate, average RR, average spread, daily risk budget)
├── StrategyGuide (Collapsible details, Kill Zone Timeline, textbook setup SVG)
├── EventStream (Terminal-style log of strategy events)
└── TradesTable (Executed trade archive with Post-Trade analysis drawers)
```

---

## 5. Data Flow Diagram

1.  **Backend Tick**: The Strategy Simulation ticks. Updates candles, recalculates OB/FVG buffers, checks session times (Kill Zones).
2.  **Signal Evaluation**: Evaluates rules: HTF Bias -> Liquidity -> CHoCH -> BOS -> OB -> FVG.
    *   *If fully qualified*: Projects a **Pending Trade Card**. After 5s, executes order.
    *   *If partially qualified but fails (e.g. outside session, or spread spike)*: Records a **Signal Rejection Event**.
3.  **Broadcasting**: Packaged payload is broadcast to connected WS clients.
4.  **UI Render**: Components receive state. Canvas/SVG rerenders candles and overlays. Chevron pipeline lights up (Green/Red/Gray).
5.  **Manual Controls**: Operator can trigger manual executions or pause pairings, sending action payloads back to the server.

---

## 6. API Design

*   `GET /api/status`: Returns current global configuration, system health state, active pairing list.
*   `GET /api/trades`: Returns historical trades list including post-trade analytics.
*   `GET /api/rejections`: Returns chronological array of rejected setups.
*   `POST /api/action`: Admin endpoint to pause/resume bots, force trade closure, or reset session stats.

---

## 7. WebSocket Schema

The server broadcasts a single unified JSON frame `TICK` containing:
```json
{
  "type": "TICK",
  "timestamp": "2026-06-30T23:01:42Z",
  "pairs": {
    "EURUSD": {
      "price": 1.0854,
      "trend": "BULLISH",
      "htfBias": "BULLISH",
      "spread": 0.8,
      "atr": 0.0014,
      "swingHigh": 1.0890,
      "swingLow": 1.0810,
      "pipeline": {
        "htfBias": { "status": "PASSED", "reason": "HTF structure supports buy orders", "time": "23:00:00" },
        "liquiditySweep": { "status": "PASSED", "reason": "Sell stops swept at 1.0815", "time": "23:01:00" },
        "choch": { "status": "PASSED", "reason": "CHoCH confirmed on 5m at 1.0832", "time": "23:01:15" },
        "bos": { "status": "PASSED", "reason": "BOS closed above 1.0845", "time": "23:01:30" },
        "orderBlock": { "status": "PASSED", "reason": "Unmitigated OB at 1.0825-1.0830", "time": "23:01:30" },
        "fvg": { "status": "PASSED", "reason": "FVG exists at 1.0830-1.0835", "time": "23:01:35" },
        "confluence": { "status": "PASSED", "reason": "Price is inside 5 pip OB buffer", "time": "23:01:40" },
        "killZone": { "status": "PASSED", "reason": "Inside London Kill Zone", "time": "23:01:40" },
        "spread": { "status": "PASSED", "reason": "0.8 pips <= 1.5 limit", "time": "23:01:40" },
        "riskCheck": { "status": "PASSED", "reason": "Risk size 1.0% is within daily cap", "time": "23:01:40" },
        "positionSize": { "status": "PASSED", "reason": "Lot size calculated: 12.5 Lots", "time": "23:01:40" },
        "ready": { "status": "PASSED", "reason": "All checks validated. Setup ready.", "time": "23:01:40" }
      },
      "activeObjects": [
        { "type": "OB", "range": "1.0825-1.0830", "strength": "HIGH", "status": "UNMITIGATED", "age": 4 },
        { "type": "FVG", "range": "1.0830-1.0835", "strength": "MEDIUM", "status": "UNMITIGATED", "age": 2 }
      ],
      "candles": [ ... ]
    }
  },
  "health": {
    "broker": { "status": "CONNECTED", "latency": 14 },
    "redis": { "status": "CONNECTED", "latency": 1 },
    "database": { "status": "CONNECTED", "latency": 2 },
    "riskEngine": { "status": "ACTIVE", "latency": 5 },
    "executionEngine": { "status": "ACTIVE", "latency": 8 },
    "strategyEngine": { "status": "ACTIVE", "latency": 12 },
    "websocket": { "status": "ACTIVE", "latency": 4 }
  },
  "analytics": {
    "signalsQualified": 45,
    "signalsRejected": 182,
    "signalsExecuted": 28,
    "winRate": 64.28,
    "avgRr": 3.2,
    "avgSpread": 0.9,
    "dailyRiskUsed": 1.5
  },
  "rejections": [ ... ],
  "activeTrade": null,
  "events": [ ... ]
}
```

---

## 8. UI Wireframes

### Main Grid Layout
```
+-------------------------------------------------------------------------------------------------------------------+
|  [LOGO] Session SMC Trading Bot Dashboard                                     (UTC) 23:01:40   [RESET STATS] [PAUSE] |
+-------------------------------------------------------------------------------------------------------------------+
|  HEALTH: Broker [14ms] ● | Redis [1ms] ● | Database [2ms] ● | Risk [5ms] ● | Exec [8ms] ● | WS [Active] ●        |
+-------------------------------------------------------------------------------------------------------------------+
|                                                                                                                   |
|  +------------------------+  +------------------------------------------------------+  +------------------------+ |
|  | PAIR SELECTOR          |  | LIVE SMC TECHNICAL CHART OVERLAY                     |  | TRADE DECISION CARD    | |
|  | [EURUSD] [GBPUSD] [USDJPY]|  | +--------------------------------------------------+ |  | +--------------------+ | |
|  |                        |  | |   _   Active Bullish Setup (1.0854)                | |  | | BUY ORDER PENDING  | | |
|  | TREND: Bullish         |  | |  |_|    OB Zone (1.0825 - 1.0830) [Green Box]      | |  | | Entry: 1.0854      | | |
|  | HTF BIAS: Bullish      |  | |        [==================================]        | |  | | SL:    1.0830      | | |
|  | Spread: 0.8 pips       |  | |   _     FVG Zone (1.0830 - 1.0835) [Cyan Box]      | |  | | TP:    1.0890      | | |
|  | ATR: 14 pips           |  | |  |_|   [==================================]        | |  | | Risk:  1.0% ($1000) | | |
|  |                        |  | |                                                    | |  | | RR:    3.2          | | |
|  +------------------------+  | |             __    __                               | |  | +--------------------+ | |
|  | SIGNAL QUALIFICATION   |  | |   __   _   |  |  |  |   <- Current price needle   | |  +------------------------+ | |
|  | Check:   Status:       |  | |  |  | | |  |__|  |__|   (1.0854)                  | |  | SESSION ANALYTICS      | | |
|  | HTF Bias [✓ PASSED]    |  | +--------------------------------------------------+ |  | Signals: 228           | | |
|  | BOS      [✓ PASSED]    |  +------------------------------------------------------+  | Win Rate: 64.2%        | | |
|  | CHoCH    [✓ PASSED]    |  | ACTIVE SMC OBJECTS                                   |  | Avg Spread: 0.9 pips   | | |
|  | OB/FVG   [✓ PASSED]    |  | Type  Range          Strength  Mitigation  Age (Cand)|  | Daily Risk: 1.5%       | | |
|  | Session  [✓ PASSED]    |  | OB    1.0825-1.0830  HIGH      Unmitigated  4 candles  |  +------------------------+ | |
|  |                        |  | FVG   1.0830-1.0835  MEDIUM    Unmitigated  2 candles  |  | SIGNAL REJECTION LOG   | | |
|  | CONFIDENCE: 92%        |  +------------------------------------------------------+  | 23:00 EURUSD Outside KZ| | |
|  +------------------------+                                                            | 22:45 GBPUSD High Spread| |
|                                                                                                                   |
+-------------------------------------------------------------------------------------------------------------------+
|  LIVE EVENT LOG (TERMINAL SCREEN)                                                                                 |
|  [23:01:40] Broadcasted tick update for EURUSD. Price active at 1.0854.                                           |
|  [23:01:35] Fair Value Gap detected on EURUSD at 1.0830 - 1.0835.                                                  |
+-------------------------------------------------------------------------------------------------------------------+
|  HISTORIC TRADES WITH POST-TRADE METRICS                                                                          |
|  Time   Pair    Type  Lots   Entry    Exit     SL       TP       PnL      Status   Latency  Slippage  Mae/Mfe     |
|  22:00  EURUSD  BUY   12.5   1.0840   1.0872   1.0815   1.0872   +$4,000  PROFIT   120ms    0.1 pips  5p / 32p    |
+-------------------------------------------------------------------------------------------------------------------+
```

---

## 9. Implementation Roadmap

1.  **Phase 1: Environment Setup & Library Installation**: Install `ws`, set up dev server to dual-boot Express + Vite.
2.  **Phase 2: Backend Simulation Loop (`server.ts`)**: Implement live price feed generators, order block trackers, event list store, and trade execution loop.
3.  **Phase 3: WS Broker Integration**: Establish server-side broadcast on client connection, handle manual reset/pause triggers.
4.  **Phase 4: Frontend WS Context (`useSocket.tsx`)**: Build auto-reconnection context, heartbeat monitor, and active state router.
5.  **Phase 5: High-Precision Renderers**:
    *   *Chart Canvas*: Draw candles, OB zones (green semitransparent), FVG zones (cyan semitransparent), SL/TP overlay lines.
    *   *Pipeline & Checklist*: Design modern chevrons and progress meters using `motion` animations.
6.  **Phase 6: Integration & Accessibility Review**: Verify 4.5+:1 color contrast ratios, screen sizing adaptivity, layout fluidity.

---

## 10. Risk Assessment

*   **Risk**: Connection dropouts.
    *   *Mitigation*: Implement client-side exponential backoff reconnection. Provide visual indicator (Red/Yellow/Green dot) on top-right of dashboard.
*   **Risk**: CPU choking during multi-candle rendering in single thread.
    *   *Mitigation*: Limit historical candles to last 35 bars. Render on HTML Canvas or optimized SVGs, debouncing canvas resizing events.
*   **Risk**: Stray processes running on container restart.
    *   *Mitigation*: Gracefully catch `SIGTERM` / `SIGINT` signals in Node server to shutdown the WS listener.

---

## 11. Performance Impact

*   **Network load**: The state is broadcast in a single compact 8KB payload every 1.5 seconds. Average bandwidth used is negligible (~5.3KB/sec).
*   **Memory overhead**: Backend tracks only 50 elements per pair, keeping heap usage under 85MB.
*   **Reflesh flickering**: Solved by disabling Vite HMR specifically during agent edits, using standard CSS transition loops for smoother animations.

---

## 12. Testing Plan

*   **Unit Tests**: Verify the SMC Strategy simulator generates correct candles and computes proper lot sizes based on stop distance.
*   **Integration Tests**: Connect a WebSocket test-client and assert correct schema parameters are returned upon `TICK` broadcast.
*   **Accessibility (A11y)**: Test readability of indicators using high-contrast dark-mode colors.
*   **Responsive tests**: Resize viewports to ensure grid cards wrap comfortably on tablet-sized displays.

---

## 13. Migration Plan

Because the previous client-side structure is empty, we migrate directly to the full-stack system:
1.  Rename original standard Vite scripts to point to the new custom `server.ts` entry point.
2.  Import Tailwind styles and lucide-react into modular layouts under `/src/components/*`.
3.  Launch new full-stack dev server utilizing `tsx`.

---

## 14. Acceptance Checklist

- [ ] Does it answer "What is the strategy doing right now?" (HTF Trend, State, Pipeline ticks)
- [ ] Does it answer "Why is it waiting?" (Rejections Log, Chevron Status = WAITING)
- [ ] Does it answer "Why did it reject a signal?" (Signal Rejections Panel with explicit rules breached)
- [ ] Does it answer "Why did it execute?" (Trade Explanation box showing all passed rules)
- [ ] Is the trading system healthy? (System heartbeats, latency counters in Header)
- [ ] Does the chart render real-time SMC elements? (Unmitigated OBs, FVGs, and SL/TP bounds overlayed)

---

## 15. Production Readiness Report

The application is structured to compile into a single-file server `dist/server.cjs` utilizing esbuild. External dependencies are handled natively. Environment files are managed via `.env.example`, ensuring a clean transition to production Cloud Run hosting on port 3000. Clock drifts are monitored, heartbeats are broadcasted dynamically, and error recovery is embedded across both layers.

This upgraded architecture represents an elite, production-grade automated trading dashboard.
