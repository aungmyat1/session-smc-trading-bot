# Component Inventory

## Summary

The React dashboard has the stronger reusable component library. The legacy dashboard has reusable layout and widget patterns, but not reusable componentized code because it is mostly one HTML file with inline JavaScript.

## React Component Inventory

| Component | Role | Reuse Verdict | Notes |
| --- | --- | --- | --- |
| `Header` | app shell, tab nav, workspace selector, theme toggle | Partial reuse | good shell pattern, but labels and nav are SVOS-specific |
| `StrategyIntake` | form for capturing strategy ideas and Gemini parsing | Not reusable for live trading | strategy intake is out of scope for live ops |
| `PipelineStageView` | lifecycle timeline and promote/demote controls | Not reusable | directly tied to validation stages |
| `AuditReportView` | defect and recommendation viewer | Not reusable | audit-stage specific |
| `ReplayView` | replay metrics, trade list, AI failure explain button | Partial reuse | tables and chart blocks reusable, replay domain is not |
| `StatisticalView` | statistical validation charts and metrics | Partial reuse | charts reusable, live trading meaning is limited |
| `RobustnessView` | robustness charts and stress scenarios | Partial reuse | useful visual patterns, wrong domain |
| `VirtualDemoView` | simulated broker feed, log console, counters | Partial reuse | terminal/log UI reusable; simulation logic is not |
| `ExecutionSafetyView` | safety checks and circuit-breaker simulation | Partial reuse | checklist and alert card patterns are reusable |
| `GovernanceView` | approval and immutable ledger tables | Not reusable | governance belongs to SVOS side |
| `VersionHistoryChart` | trend visualization and comparison overlay | Partial reuse | charting patterns reusable for equity/PnL/performance |
| `FullPipelineReport` | detailed multi-stage report renderer | Not reusable | entirely SVOS pipeline-oriented |

## Legacy UI Pattern Inventory

| Pattern | Where | Reuse Verdict | Notes |
| --- | --- | --- | --- |
| Header with system status | legacy top bar | Reusable | strong fit for live ops |
| Metric cards | status bar, RGM, Governance, SMO | Reusable | should be rebuilt as components |
| Panel/card layout | all legacy sections | Reusable | simple and effective |
| Badge system | statuses across legacy panel | Reusable | useful for live/alert/watch/healthy states |
| Tables | strategy table, trade journal | Reusable | trade journal table especially useful |
| Filter chips | incident feed | Reusable | simple and portable |
| Output viewer | reports/SVOS output box | Partial reuse | useful for logs and reports |
| Modal/dialogs | none | Missing | would need to be added |
| Notifications/toasts | browser `alert()` in React, inline outputs in legacy | Needs work | no production notification system |
| Sidebar navigation | none | Missing | current navigation is tabs or stacked panels |

## Feature Class Inventory

### Cards

- Present in both implementations
- Strong candidate for reuse

### Tables

- Present in both implementations
- Best reusable cases:
  - trade journal table
  - governance ledger table structure
  - metrics tables from `FullPipelineReport`

### Charts

- Present mainly in React via `recharts`
- Useful reusable components:
  - line charts
  - area charts
  - comparative trend charts
- Missing for live trading:
  - candlestick charts
  - depth/order book charts
  - broker latency time series fed from real data

### Navigation

- Legacy: no route-based page navigation
- React: internal tab navigation only
- For a production live dashboard, reusable only as a starting shell

### Forms

- Present in React strategy intake and control actions in legacy
- Reusable patterns exist, but current semantics are wrong for live ops

### Dialogs / Modals

- No real modal system
- Missing for production-grade confirmations, order actions, and sensitive controls

### Notifications

- Missing proper notification architecture
- current use of:
  - inline status text
  - browser `alert()`
- Not acceptable for industrial live operations

### TradingView integration

- No TradingView integration found
- No embedded chart widget found
- Missing completely

### Theme system

- React has light/dark mode toggle with localStorage persistence
- Legacy has a fixed dark theme
- React theme shell is reusable

### Layout / responsiveness

- React has much better responsive behavior with grid classes and overflow handling
- Legacy has some responsive CSS but remains a dense desktop-first control panel

## State and Interaction Patterns

### Good reusable patterns

- polling refresh dashboard shell
- status badge language
- side-by-side metrics plus logs
- chart + summary card combinations
- incident filtering

### Poor patterns for production reuse

- direct `fetch()` calls from components
- component-local API orchestration
- no domain API client
- no auth/session layer
- no websocket subscription abstraction
- no error-boundary or retry model

## Recommended Keep/Discard

### Keep

- React chart components as presentation-only shells
- React header and responsive card patterns
- Legacy trade journal, incident feed, and status bar concepts
- Legacy emergency-stop control layout

### Discard

- validation-stage navigation model
- local simulation widgets
- Gemini-driven strategy intake
- local overlay-backed governance/editor flows
- single-file legacy page implementation
