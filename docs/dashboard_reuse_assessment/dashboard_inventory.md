# Dashboard Inventory

## Summary

The repository exposes two dashboard surfaces.

1. Legacy control panel at `/legacy`
2. React SPA at `/new-dashboard/`

The first is closer to live operations. The second is closer to a strategy-validation workbench.

## Page Inventory

| Surface | Route | Purpose | Main Components / Sections | APIs Used | Reusable Status |
| --- | --- | --- | --- | --- | --- |
| Legacy redirect | `/` | Redirects users to the React dashboard | none | none | Not a page |
| Legacy control panel | `/legacy` | Single-page operational control panel combining SVOS, EVF, runtime, reports, incidents, and journal views | status bar, SVOS panel, EVF panel, RGM panel, Governance panel, SMO panel, Reports Center, Vantage Demo Runtime, Trade Journal, Incident Log | `/api/status`, `/api/svos`, `/api/evf`, `/api/rgm`, `/api/governance`, `/api/smo`, `/api/reports/latest`, `/api/reports/*`, `/api/demo-runner`, `/api/trades`, action endpoints for reports, incidents, SVOS, EVF, emergency stop | Partial reuse |
| New dashboard SPA shell | `/new-dashboard/` | React single-page app for strategy lifecycle and validation evidence | header, strategy selector, tabs, strategy intake, stage banner, reports and validation views | `/api/new-dashboard/*`, Gemini helper endpoints | Partial reuse at component level only |
| New dashboard assets | `/new-dashboard/<path>` | Serves built SPA assets or fallback document | static assets | none | Infrastructure only |

## Legacy Control Panel Sections

### 1. Status bar

- Purpose: top-level operational summary
- Includes:
  - current strategy
  - SVOS status
  - EVF score/status
  - trade count and win rate
  - RGM status
  - governance status
  - SMO status
  - live/demo/paper badge
  - emergency-stop state
- APIs:
  - `/api/status`
- Reusable:
  - Yes for a live dashboard
- Caveat:
  - current fields are strategy-governance oriented, not account/portfolio oriented

### 2. SVOS Research and Verification

- Purpose: display strategy validation progress and allow SVOS runs
- APIs:
  - `/api/svos`
  - `/api/svos/run`
  - `/api/reports/<report_id>`
- Reusable:
  - No for live trading dashboard
- Reason:
  - SVOS must remain separate by requirement

### 3. EVF Execution Validation

- Purpose: show execution validation evidence and trigger EVF run
- APIs:
  - `/api/evf`
  - `/api/evf/run`
- Reusable:
  - Limited
- Reason:
  - useful as a support view for pre-live validation, but not core live operations UI

### 4. RGM Risk Qualification

- Purpose: display risk and portfolio guard states plus emergency-stop controls
- APIs:
  - `/api/rgm`
  - `/api/emergency-stop`
  - `/api/emergency-stop/clear`
- Reusable:
  - Yes, with backend replacement
- Notes:
  - currently reads local health snapshots and writes local control-state

### 5. Governance Control Plane

- Purpose: summarize approval and promotion state
- APIs:
  - `/api/governance`
- Reusable:
  - No for live trading dashboard core
- Reason:
  - governance is SVOS-side control-plane functionality

### 6. SMO Monitoring

- Purpose: monitoring summary for runner, database, incidents, and emergency state
- APIs:
  - `/api/smo`
- Reusable:
  - Yes, partially
- Notes:
  - incident logic is log-file based and should be replaced with production monitoring streams or APIs

### 7. Reports Center

- Purpose: browse generated reports, open latest report, mark review state, and trigger report generation
- APIs:
  - `/api/reports/latest`
  - `/api/reports/<report_id>`
  - `/api/reports/generate`
  - `/api/reports/generate/all`
  - `/api/reports/<report_id>/review`
- Reusable:
  - Partial
- Notes:
  - report viewer UI is reusable
  - current report-generation backend is tightly coupled to local scripts and files

### 8. Vantage Demo Runtime

- Purpose: show runtime status, demo account state, signals, and open positions
- APIs:
  - `/api/demo-runner`
- Reusable:
  - Yes, conceptually
- Notes:
  - this is the closest legacy section to a live operations dashboard
  - currently it is demo-runner specific, not generalized broker/portfolio state

### 9. Trade Journal

- Purpose: list recent closed trades and summary stats
- APIs:
  - `/api/trades`
- Reusable:
  - Yes
- Notes:
  - needs replacement with production order/trade history services

### 10. Incident / Alert Log

- Purpose: view alerts, audit events, and control events; acknowledge incidents
- APIs:
  - `/api/smo`
  - `/api/incidents/ack`
- Reusable:
  - Yes
- Notes:
  - strong candidate for reuse after replacing the log-file backend

## React SPA Tab Inventory

The React app is a single route with internal tab navigation.

| Tab | Purpose | Main Components | APIs Used | Reusable Status |
| --- | --- | --- | --- | --- |
| Intake & Registry | strategy registry and workspace selector | `Header`, `PipelineStageView`, `StrategyIntake`, `VersionHistoryChart` | `/api/new-dashboard/strategies`, `/api/new-dashboard/gemini/parse`, create/update/promote/demote endpoints | Partial |
| Full Pipeline Report | full SVOS pipeline report viewer | `FullPipelineReport` | `/api/new-dashboard/strategies/<id>/pipeline-report` | Not reusable for live trading |
| AI Audit & Refinement | audit defect review and simulated fixes | `AuditReportView` | `/api/new-dashboard/strategies/<id>` | Not reusable |
| Historical Replay & Stats | replay and statistical validation evidence | `ReplayView`, `StatisticalView` | strategy payload only, plus `/api/new-dashboard/gemini/explain-failure` for failure explanation | Partial chart/table reuse only |
| Robustness & Stress Test | robustness evidence review | `RobustnessView` | strategy payload only | Partial chart/card reuse only |
| Virtual Demo Simulator | simulated broker tick/feed and logs | `VirtualDemoView` | no realtime backend, local interval simulation | Not reusable as implemented |
| Execution & Safety | simulated execution safety checks | `ExecutionSafetyView` | strategy payload only | Partial card/list reuse only |
| Governance & Ledger | approval and audit ledger viewer | `GovernanceView` | strategy payload only | Not reusable for live trading core |

## Reuse Status Legend

- Reusable: can migrate with moderate backend remapping
- Partial reuse: visual or component structure is useful, but behavior and data model are not
- Not reusable: tightly aligned to SVOS/EVF strategy validation rather than live trading operations
