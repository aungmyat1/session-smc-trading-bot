# ISOP Control Panel

The dashboard in `dashboard/` is extended in place as the ISOP Control Panel.

It preserves the existing SVOS, EVF, trades, and status behavior while adding:

- RGM risk qualification view
- Governance control-plane view
- SMO monitoring and incident view
- Reports center backed by `scripts/generate_reports.py`
- Emergency control state with confirm-token protection
- Audit logging for dashboard-triggered actions
- Supported-symbol visibility through `GET /api/symbols`, including separate research and execution eligibility

Primary backend files:

- `dashboard/app.py`
- `dashboard/report_service.py`
- `dashboard/control_state.py`
- `dashboard/audit_log.py`
- `dashboard/status_mapper.py`

Primary UI file:

- `dashboard/index.html`

Safety notes:

- No live-trading enable path is added.
- Report generation is read-only and writes only report artifacts.
- Emergency stop changes dashboard control state and audit logs only.
- Existing SVOS/EVF confirm-token behavior remains in place.
- BTCUSDT is displayed as crypto and research-only; the dashboard does not provide an execution-enable control.
