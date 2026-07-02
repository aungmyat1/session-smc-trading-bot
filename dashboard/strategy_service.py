"""
New-dashboard strategy service.

Bridges the UI's Strategy schema with the SVOS catalog (YAML) and report
files.  Writes go through a JSON overlay so SVOS run-reports stay immutable.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_CATALOG_PATH = _ROOT / "config" / "strategy_catalog.yaml"
_SVOS_DIR = _ROOT / "reports" / "svos"
_OVERLAY_PATH = _ROOT / "reports" / "dashboard_strategies.json"

# ── Stage name constants (must match types.ts ValidationStage enum values) ────

_STAGE_INTAKE = "Strategy Intake"
_STAGE_AUDIT = "Strategy Audit"
_STAGE_REFINEMENT = "AI Strategy Refinement"
_STAGE_REPLAY = "Historical Replay"
_STAGE_STATISTICAL = "Statistical Validation"
_STAGE_ROBUSTNESS = "Robustness Validation"
_STAGE_VIRTUAL_DEMO = "Virtual Demo Validation"
_STAGE_VERIFICATION_READY = "Verification Ready"
_STAGE_EXECUTION = "Execution Validation"
_STAGE_LIVE_DEMO = "Live Demo"
_STAGE_PRODUCTION = "Production Approval"

# Maps catalog/SVOS status strings → UI ValidationStage string
_STATUS_TO_UI_STAGE: dict[str, str] = {
    "DEFERRED_REVALIDATION": _STAGE_INTAKE,
    "draft":                 _STAGE_INTAKE,
    "intake":                _STAGE_INTAKE,
    "INTAKE":                _STAGE_INTAKE,
    "research":              _STAGE_AUDIT,
    "audit":                 _STAGE_AUDIT,
    "AUDIT":                 _STAGE_AUDIT,
    "refinement":            _STAGE_REFINEMENT,
    "REFINEMENT":            _STAGE_REFINEMENT,
    "replay":                _STAGE_REPLAY,
    "historical_replay":     _STAGE_REPLAY,
    "HISTORICAL_REPLAY":     _STAGE_REPLAY,
    "backtest":              _STAGE_STATISTICAL,
    "statistical_validation": _STAGE_STATISTICAL,
    "STATISTICAL_VALIDATION": _STAGE_STATISTICAL,
    "robustness":            _STAGE_ROBUSTNESS,
    "walk_forward":          _STAGE_ROBUSTNESS,
    "robustness_validation": _STAGE_ROBUSTNESS,
    "ROBUSTNESS_VALIDATION": _STAGE_ROBUSTNESS,
    "virtual_demo":          _STAGE_VIRTUAL_DEMO,
    "shadow":                _STAGE_VIRTUAL_DEMO,
    "VIRTUAL_DEMO":          _STAGE_VIRTUAL_DEMO,
    "demo":                  _STAGE_VERIFICATION_READY,
    "verification_ready":    _STAGE_VERIFICATION_READY,
    "VERIFICATION_READY":    _STAGE_VERIFICATION_READY,
    "execution_validation":  _STAGE_EXECUTION,
    "EXECUTION_VALIDATION":  _STAGE_EXECUTION,
    "live_demo":             _STAGE_LIVE_DEMO,
    "LIVE_DEMO":             _STAGE_LIVE_DEMO,
    "production_approval":   _STAGE_PRODUCTION,
    "PRODUCTION_APPROVAL":   _STAGE_PRODUCTION,
}

# Maps UI stage → lifecycle manager stage (for promote/demote)
_UI_STAGE_TO_LC: dict[str, str] = {
    _STAGE_INTAKE:              "INTAKE",
    _STAGE_AUDIT:               "AUDIT",
    _STAGE_REFINEMENT:          "REFINEMENT",
    _STAGE_REPLAY:              "HISTORICAL_REPLAY",
    _STAGE_STATISTICAL:         "STATISTICAL_VALIDATION",
    _STAGE_ROBUSTNESS:          "ROBUSTNESS_VALIDATION",
    _STAGE_VIRTUAL_DEMO:        "VIRTUAL_DEMO",
    _STAGE_VERIFICATION_READY:  "VIRTUAL_DEMO",
    _STAGE_EXECUTION:           "VIRTUAL_DEMO",
    _STAGE_PRODUCTION:          "PRODUCTION_APPROVAL",
}

_UI_STAGE_ORDER = [
    _STAGE_INTAKE, _STAGE_AUDIT, _STAGE_REFINEMENT, _STAGE_REPLAY,
    _STAGE_STATISTICAL, _STAGE_ROBUSTNESS, _STAGE_VIRTUAL_DEMO,
    _STAGE_VERIFICATION_READY, _STAGE_EXECUTION, _STAGE_LIVE_DEMO,
    _STAGE_PRODUCTION,
]


# ── Overlay persistence ───────────────────────────────────────────────────────

def _load_overlay() -> dict[str, Any]:
    if _OVERLAY_PATH.exists():
        try:
            return json.loads(_OVERLAY_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"strategies": {}}


def _save_overlay(overlay: dict[str, Any]) -> None:
    _OVERLAY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OVERLAY_PATH.write_text(json.dumps(overlay, indent=2, default=str))


# ── Catalog helpers ───────────────────────────────────────────────────────────

def _load_catalog() -> dict[str, Any]:
    try:
        import yaml
        return yaml.safe_load(_CATALOG_PATH.read_text()) or {}
    except Exception:
        return {}


def _save_catalog(catalog: dict[str, Any]) -> None:
    try:
        import yaml
        _CATALOG_PATH.write_text(yaml.dump(catalog, default_flow_style=False, allow_unicode=True))
    except Exception:
        pass


# ── SVOS run helpers ──────────────────────────────────────────────────────────

def _latest_svos_run(strategy_name: str) -> Path | None:
    """Return path to the most recent run directory for *strategy_name*."""
    base = _SVOS_DIR / strategy_name
    if not base.exists():
        return None
    runs: list[Path] = []
    for version_dir in base.iterdir():
        if not version_dir.is_dir():
            continue
        for run_dir in version_dir.iterdir():
            if run_dir.is_dir() and (run_dir / "run_summary.json").exists():
                runs.append(run_dir)
    if not runs:
        return None
    return max(runs, key=lambda p: p.name)


def _load_stage_json(run_dir: Path, prefix: str) -> dict[str, Any] | None:
    """Load the first JSON file whose name starts with *prefix* in *run_dir*."""
    for f in sorted(run_dir.glob(f"{prefix}*.json")):
        try:
            return json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return None


# ── Evidence mappers ──────────────────────────────────────────────────────────

def _map_audit(run_summary_stage: dict, stage_data: dict) -> dict[str, Any]:
    """Map 01_strategy_audit.json → AuditReport schema."""
    findings = stage_data.get("findings", [])
    hard_gates = stage_data.get("hard_gate_results", [])
    defects = []
    for i, f in enumerate(findings):
        defects.append({
            "id": f"defect-{i}",
            "type": f.get("type", "ambiguity"),
            "severity": "high" if f.get("blocker") else "medium",
            "title": str(f.get("message", f.get("name", "Issue"))),
            "description": str(f.get("detail", f.get("description", ""))),
            "affectedRule": str(f.get("field", f.get("rule", ""))),
        })
    recommendations = [g["message"] for g in hard_gates if not g.get("passed")]
    return {
        "checkedAt": stage_data.get("generated_at", ""),
        "isPassed": stage_data.get("status") == "PASS",
        "score": float(run_summary_stage.get("score", stage_data.get("score", 0))),
        "logicalDefects": defects,
        "recommendations": recommendations,
    }


def _map_replay(stage_data: dict, backtest_data: dict | None) -> dict[str, Any]:
    """Map 02_historical_replay.json + 03_backtest.json → ReplayReport schema."""
    metrics = (backtest_data or {}).get("metrics", {})
    inner = metrics.get("metrics", metrics)  # backtest nests metrics.metrics
    trade_count = int(inner.get("trade_count", 0))
    win_rate = float(inner.get("win_rate", 0))
    return {
        "runAt": stage_data.get("generated_at", ""),
        "periodStart": stage_data.get("period_start", stage_data.get("generated_at", "")),
        "periodEnd": stage_data.get("period_end", stage_data.get("generated_at", "")),
        "totalTrades": trade_count,
        "winningTrades": int(trade_count * win_rate),
        "losingTrades": trade_count - int(trade_count * win_rate),
        "winRate": win_rate,
        "profitFactor": float(inner.get("profit_factor", 0)),
        "maxDrawdown": float(inner.get("max_drawdown", 0)) / 100,
        "totalReturnPct": float(inner.get("net_return", inner.get("total_return", 0))),
        "equityCurve": [],
        "trades": [],
    }


def _map_statistics(stage_data: dict) -> dict[str, Any]:
    """Map 03_backtest.json → StatisticalReport schema."""
    metrics = stage_data.get("metrics", {})
    inner = metrics.get("metrics", metrics)
    return {
        "validatedAt": stage_data.get("generated_at", ""),
        "sharpeRatio": float(inner.get("sharpe_ratio", inner.get("expectancy", 0))),
        "sortinoRatio": float(inner.get("sortino_ratio", 0)),
        "tStat": float(inner.get("t_stat", 0)),
        "pValue": float(inner.get("p_value", 0)),
        "isPassed": stage_data.get("status") == "PASS",
        "monteCarloPercentiles": {
            "p10": float(inner.get("mc_p10", 0)),
            "p50": float(inner.get("mc_p50", inner.get("net_return", 0))),
            "p90": float(inner.get("mc_p90", 0)),
        },
        "regimePerformance": {
            "bullMarketReturnPct": float(inner.get("bull_return", 0)),
            "bearMarketReturnPct": float(inner.get("bear_return", 0)),
            "highVolatilityReturnPct": float(inner.get("high_vol_return", 0)),
            "lowVolatilityReturnPct": float(inner.get("low_vol_return", 0)),
        },
    }


def _map_robustness(stage_data: dict) -> dict[str, Any]:
    """Map 04_robustness.json → RobustnessReport schema."""
    hard_gates = stage_data.get("hard_gate_results", [])
    metrics = stage_data.get("metrics", {})
    return {
        "testedAt": stage_data.get("generated_at", ""),
        "parameterSensitivity": {
            "parameterName": "shortPeriod",
            "sweepPoints": [],
        },
        "stressScenarios": [
            {
                "name": g["name"],
                "description": g.get("message", ""),
                "returnPct": 0.0,
                "maxDrawdownPct": 0.0,
                "notes": "PASS" if g.get("passed") else "FAIL",
            }
            for g in hard_gates
        ],
        "noiseTestPassed": all(g.get("passed") for g in hard_gates),
        "slippageSensitivityPct": float(metrics.get("slippage_sensitivity", 0)),
    }


def _map_virtual_demo(stage_data: dict) -> dict[str, Any]:
    """Map 05_virtual_demo.json → VirtualDemoReport schema."""
    metrics = stage_data.get("metrics", {})
    days = float(metrics.get("days_monitored", 0))
    execution = metrics.get("execution", {})
    exec_metrics = execution.get("execution_metrics", {})
    outcomes = execution.get("order_outcomes", {})
    return {
        "startedAt": stage_data.get("generated_at", ""),
        "durationHours": days * 24,
        "simulatedOrdersSubmitted": int(execution.get("expected_trades", 0)),
        "simulatedOrdersFilled": int(execution.get("observed_trades", 0)),
        "simulatedOrdersRejected": int(outcomes.get("rejected", 0)),
        "averageLatencyMs": float(exec_metrics.get("latency_ms", 0)),
        "slippageCostPct": float(exec_metrics.get("slippage_pips", 0)) * 0.01,
        "simulatedProfitPct": 0.0,
        "executionLogs": [],
    }


def _map_execution_safety(stage_data: dict) -> dict[str, Any]:
    """Map 05_virtual_demo.json execution section → ExecutionSafetyReport schema."""
    metrics = stage_data.get("metrics", {})
    execution = metrics.get("execution", {})
    exec_metrics = execution.get("execution_metrics", {})
    risk_controls = execution.get("risk_controls", {})
    exp_signals = int(execution.get("expected_signals", 0))
    obs_signals = int(execution.get("observed_signals", 0))
    integrity = 100.0 if exp_signals == 0 else round(obs_signals / exp_signals * 100, 1)
    checks = []
    for label, key in [
        ("Position Sizing", "position_sizing"),
        ("Daily Loss Limit", "daily_loss_limit"),
        ("Max Open Positions", "maximum_open_positions"),
    ]:
        passed = bool(risk_controls.get(key))
        checks.append({
            "ruleName": label,
            "description": f"{label} risk control",
            "status": "PASSED" if passed else "FAILED",
            "actualValue": "Enforced" if passed else "Not enforced",
            "thresholdValue": "Required",
        })
    return {
        "testedAt": stage_data.get("generated_at", ""),
        "signalIntegrityScore": integrity,
        "apiLatencyP99Ms": float(exec_metrics.get("latency_ms", 0)),
        "circuitBreakerTriggered": False,
        "reconnectionSuccessRatePct": 100.0,
        "safetyChecks": checks,
    }


def _map_production_approval(stage_data: dict) -> dict[str, Any]:
    """Map 06_production_approval.json → ProductionApprovalReport schema."""
    metrics = stage_data.get("metrics", {})
    approved = bool(metrics.get("registry_approved", False))
    return {
        "approvedAt": stage_data.get("generated_at", ""),
        "governanceHash": stage_data.get("evidence_hashes", {}).get("strategy_spec", ""),
        "certificateId": stage_data.get("report_id", ""),
        "signoffs": [
            {
                "role": "Platform Validation System",
                "approver": "SVOS",
                "signedAt": stage_data.get("generated_at", ""),
                "comments": "All validation stages passed via SVOS pipeline",
                "approved": approved,
            }
        ],
        "riskCapLimitUsd": 10000,
    }


# ── Strategy builder ──────────────────────────────────────────────────────────

def _build_evidence(run_dir: Path | None, run_summary: dict | None) -> dict[str, Any]:
    """Build the evidence tree from a SVOS run directory."""
    evidence: dict[str, Any] = {}
    if run_dir is None or run_summary is None:
        return evidence

    stages_index = {s["stage"]: s for s in run_summary.get("stages", [])}

    audit_data = _load_stage_json(run_dir, "01_")
    if audit_data:
        evidence["audit"] = _map_audit(stages_index.get("strategy_audit", {}), audit_data)

    replay_data = _load_stage_json(run_dir, "02_")
    backtest_data = _load_stage_json(run_dir, "03_")
    if replay_data:
        evidence["replay"] = _map_replay(replay_data, backtest_data)
    if backtest_data:
        evidence["statistics"] = _map_statistics(backtest_data)

    robustness_data = _load_stage_json(run_dir, "04_")
    if robustness_data:
        evidence["robustness"] = _map_robustness(robustness_data)

    vdemo_data = _load_stage_json(run_dir, "05_")
    if vdemo_data:
        evidence["virtualDemo"] = _map_virtual_demo(vdemo_data)
        evidence["executionSafety"] = _map_execution_safety(vdemo_data)

    approval_data = _load_stage_json(run_dir, "06_")
    if approval_data:
        evidence["productionApproval"] = _map_production_approval(approval_data)

    return evidence


def _build_audit_log(run_summary: dict | None) -> list[dict]:
    """Build governance records from SVOS stage results."""
    if not run_summary:
        return []
    records = []
    prev_stage = "NONE"
    for stage in run_summary.get("stages", []):
        ui_stage = _STATUS_TO_UI_STAGE.get(stage.get("stage", ""), _STAGE_INTAKE)
        raw_score = stage.get("score", 0)
        try:
            score_text = f"{float(raw_score):.1f}"
        except (TypeError, ValueError):
            score_text = "n/a"
        records.append({
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, stage.get("report_id", stage.get("stage", "")))),
            "timestamp": run_summary.get("generated_at", ""),
            "actor": "SVOS",
            "action": "stage_validated",
            "fromStage": _STATUS_TO_UI_STAGE.get(prev_stage, "NONE") if prev_stage != "NONE" else "NONE",
            "toStage": ui_stage,
            "hash": stage.get("report_id", ""),
            "evidenceSummary": f"{stage.get('stage_label', '')} — score {score_text}",
            "details": stage.get("status", ""),
        })
        prev_stage = stage.get("stage", "")
    return records


def _catalog_meta_to_strategy(
    name: str,
    meta: dict[str, Any],
    overlay: dict[str, Any],
) -> dict[str, Any]:
    """Convert a catalog entry + optional SVOS run into a Strategy object."""
    ovr = (overlay.get("strategies") or {}).get(name, {})

    run_dir = _latest_svos_run(name)
    run_summary: dict | None = None
    if run_dir:
        try:
            run_summary = json.loads((run_dir / "run_summary.json").read_text())
        except (OSError, json.JSONDecodeError):
            run_summary = None

    # Determine status: prefer authoritative SVOS latest_passed_stage, then
    # catalog value, then overlay UI annotations. Overlay remains for user
    # edits but must not override SVOS validation state.
    if run_summary and run_summary.get("latest_passed_stage"):
        status = _STATUS_TO_UI_STAGE.get(run_summary["latest_passed_stage"], _STAGE_INTAKE)
    elif meta and meta.get("status"):
        status = _STATUS_TO_UI_STAGE.get(str(meta.get("status", "intake")), _STAGE_INTAKE)
    elif ovr.get("status"):
        status = ovr["status"]
    else:
        status = _STAGE_INTAKE

    symbols = meta.get("symbols", [])
    timeframes = meta.get("timeframes", [])

    rules = ovr.get("rules") or {
        "assetClass": "Forex",
        "symbol": symbols[0] if symbols else "",
        "timeframe": timeframes[0] if timeframes else "",
        "entryConditions": [],
        "exitConditions": [],
        "riskRules": {
            "stopLossPct": 1.0,
            "takeProfitPct": 2.0,
            "maxPositionSizePct": 2.0,
            "dailyLossLimitPct": 3.0,
        },
        "parameters": {},
    }

    evidence = _build_evidence(run_dir, run_summary)
    # Merge any overlay evidence patches on top
    if ovr.get("evidence"):
        for k, v in ovr["evidence"].items():
            if v is not None:
                evidence[k] = v

    created_at = meta.get("created_at", run_summary.get("generated_at", "") if run_summary else "")
    version = str(meta.get("version", run_summary.get("strategy_version", "1.0.0") if run_summary else "1.0.0"))

    audit_log = _build_audit_log(run_summary)
    if ovr.get("auditLog"):
        audit_log = ovr["auditLog"] + audit_log

    return {
        "id": name,
        "name": ovr.get("name", meta.get("display_name", name)),
        "version": version,
        "description": ovr.get("description", meta.get("description", "")),
        "author": ovr.get("author", meta.get("owner", "quant")),
        "createdAt": created_at,
        "updatedAt": run_summary.get("generated_at", created_at) if run_summary else created_at,
        "status": status,
        "rules": rules,
        "evidence": evidence,
        "auditLog": audit_log,
        "versionHistory": ovr.get("versionHistory", []),
    }


# ── Public API ────────────────────────────────────────────────────────────────

def list_strategies() -> list[dict[str, Any]]:
    """Return all strategies as Strategy[] for the new dashboard."""
    catalog = _load_catalog()
    overlay = _load_overlay()
    result: list[dict[str, Any]] = []

    # Strategies from catalog
    seen: set[str] = set()
    for name, meta in (catalog.get("strategies") or {}).items():
        if not isinstance(meta, dict):
            meta = {}
        result.append(_catalog_meta_to_strategy(name, meta, overlay))
        seen.add(name)

    # Strategies only in SVOS reports dir (e.g. SVOS-SAMPLE)
    if _SVOS_DIR.exists():
        for svos_dir in _SVOS_DIR.iterdir():
            if svos_dir.is_dir() and svos_dir.name not in seen and svos_dir.name != "platform":
                result.append(_catalog_meta_to_strategy(svos_dir.name, {}, overlay))
                seen.add(svos_dir.name)

    # Strategies only in overlay (UI-created, not yet in catalog)
    for name, ovr_entry in (overlay.get("strategies") or {}).items():
        if name not in seen:
            result.append(ovr_entry)
            seen.add(name)

    return result


def get_strategy(strategy_id: str) -> dict[str, Any] | None:
    """Return a single Strategy by id, or None if not found."""
    catalog = _load_catalog()
    overlay = _load_overlay()
    strategies = catalog.get("strategies") or {}

    if strategy_id in strategies:
        meta = strategies[strategy_id]
        if not isinstance(meta, dict):
            meta = {}
        return _catalog_meta_to_strategy(strategy_id, meta, overlay)

    # Check SVOS reports dir
    if (_SVOS_DIR / strategy_id).exists():
        return _catalog_meta_to_strategy(strategy_id, {}, overlay)

    # Check overlay-only
    ovr = (overlay.get("strategies") or {}).get(strategy_id)
    if ovr:
        return ovr

    return None


def create_strategy(data: dict[str, Any]) -> dict[str, Any]:
    """Create a new strategy. Adds to overlay (not catalog — catalog writes require SVOS run)."""
    overlay = _load_overlay()
    strategy_id = data.get("name", "").replace(" ", "-").upper() or str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()

    strategy: dict[str, Any] = {
        "id": strategy_id,
        "name": data.get("name", strategy_id),
        "version": "0.1",
        "description": data.get("description", ""),
        "author": data.get("author", "quant"),
        "createdAt": now,
        "updatedAt": now,
        "status": _STAGE_INTAKE,
        "rules": data.get("rules") or {
            "assetClass": "Forex",
            "symbol": "",
            "timeframe": "",
            "entryConditions": [],
            "exitConditions": [],
            "riskRules": {
                "stopLossPct": 1.0,
                "takeProfitPct": 2.0,
                "maxPositionSizePct": 2.0,
                "dailyLossLimitPct": 3.0,
            },
            "parameters": {},
        },
        "evidence": {},
        "auditLog": [
            {
                "id": str(uuid.uuid4()),
                "timestamp": now,
                "actor": data.get("author", "quant"),
                "action": "strategy_created",
                "fromStage": "NONE",
                "toStage": _STAGE_INTAKE,
                "hash": "",
                "evidenceSummary": "Strategy registered in platform",
                "details": data.get("description", ""),
            }
        ],
        "versionHistory": [],
    }

    overlay.setdefault("strategies", {})[strategy_id] = strategy
    _save_overlay(overlay)
    return strategy


def update_strategy(strategy_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    """Patch evidence fields in overlay (used by apply-fix workflow)."""
    overlay = _load_overlay()
    ovr_strategies = overlay.setdefault("strategies", {})

    # Merge patch into overlay for this strategy
    entry = ovr_strategies.get(strategy_id, {})
    if "evidence" in patch:
        entry.setdefault("evidence", {}).update(patch["evidence"])
    if "rules" in patch:
        entry["rules"] = patch["rules"]
    if "status" in patch:
        entry["status"] = patch["status"]
    entry["updatedAt"] = datetime.now(timezone.utc).isoformat()
    ovr_strategies[strategy_id] = entry
    _save_overlay(overlay)

    return get_strategy(strategy_id)


def promote_strategy(strategy_id: str) -> dict[str, Any] | None:
    """Advance strategy to the next validation stage."""
    strategy = get_strategy(strategy_id)
    if not strategy:
        return None

    current_ui = strategy["status"]
    idx = _UI_STAGE_ORDER.index(current_ui) if current_ui in _UI_STAGE_ORDER else -1
    if idx < 0 or idx >= len(_UI_STAGE_ORDER) - 1:
        return strategy  # already at final stage

    next_ui = _UI_STAGE_ORDER[idx + 1]
    now = datetime.now(timezone.utc).isoformat()

    # Try the SVOS platform lifecycle manager first
    try:
        from svos.orchestration.service import SVOSPlatform, PersistenceMode
        platform = SVOSPlatform(root=_ROOT, persistence_mode=PersistenceMode.LOCAL_COMPAT)
        platform.bootstrap()
        next_lc = _UI_STAGE_TO_LC.get(next_ui, "")
        if next_lc:
            platform.audited_transition(
                strategy_id,
                to_stage=next_lc,
                actor="dashboard",
                reason=f"Promoted via new dashboard to {next_ui}",
            )
    except Exception:
        pass  # lifecycle manager unavailable or strategy not in catalog — fall through to overlay

    # Update overlay status regardless
    overlay = _load_overlay()
    ovr_strategies = overlay.setdefault("strategies", {})
    entry = ovr_strategies.get(strategy_id, {})
    entry["status"] = next_ui
    entry["updatedAt"] = now
    entry.setdefault("auditLog", []).append({
        "id": str(uuid.uuid4()),
        "timestamp": now,
        "actor": "dashboard",
        "action": "stage_promoted",
        "fromStage": current_ui,
        "toStage": next_ui,
        "hash": "",
        "evidenceSummary": f"Promoted from {current_ui} to {next_ui}",
        "details": "",
    })
    ovr_strategies[strategy_id] = entry
    _save_overlay(overlay)

    return get_strategy(strategy_id)


def get_pipeline_report(strategy_id: str) -> dict[str, Any] | None:
    """Return raw SVOS stage data for the full pipeline report view."""
    run_dir = _latest_svos_run(strategy_id)
    if run_dir is None:
        return None

    try:
        run_summary = json.loads((run_dir / "run_summary.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None

    stage_files = [
        ("01_", "strategy_audit",      "Strategy Audit",       1),
        ("02_", "historical_replay",   "Historical Replay",    2),
        ("03_", "backtest",            "Backtest",             3),
        ("04_", "robustness",          "Robustness Tests",     4),
        ("05_", "virtual_demo",        "Virtual Demo",         5),
        ("06_", "production_approval", "Production Approval",  6),
    ]

    stages_out = []
    stages_index = {s["stage"]: s for s in run_summary.get("stages", [])}

    for prefix, stage_key, label, num in stage_files:
        data = _load_stage_json(run_dir, prefix)
        if data is None:
            continue
        summary_entry = stages_index.get(stage_key, {})
        stages_out.append({
            "stage_num":        num,
            "stage":            stage_key,
            "stage_label":      label,
            "status":           data.get("status", summary_entry.get("status", "PENDING")),
            "score":            float(summary_entry.get("score", data.get("score", 0))),
            "promotion_allowed": bool(summary_entry.get("promotion_allowed", data.get("promotion_allowed", False))),
            "generated_at":     data.get("generated_at", run_summary.get("generated_at", "")),
            "metrics":          data.get("metrics", {}),
            "findings":         data.get("findings", []),
            "hard_gate_results": data.get("hard_gate_results", []),
            "warnings":         data.get("warnings", []),
            "remediation":      data.get("remediation", []),
        })

    return {
        "strategy_id":       run_summary.get("strategy_id", strategy_id),
        "strategy_name":     run_summary.get("strategy_name", strategy_id),
        "strategy_version":  run_summary.get("strategy_version", ""),
        "run_id":            run_summary.get("run_id", ""),
        "generated_at":      run_summary.get("generated_at", ""),
        "overall_status":    run_summary.get("overall_status", ""),
        "latest_passed_stage": run_summary.get("latest_passed_stage", ""),
        "stages":            stages_out,
    }


def demote_strategy(strategy_id: str, target_stage: str, reason: str) -> dict[str, Any] | None:
    """Regress strategy to a prior stage."""
    strategy = get_strategy(strategy_id)
    if not strategy:
        return None

    current_ui = strategy["status"]
    now = datetime.now(timezone.utc).isoformat()

    # Try lifecycle manager
    try:
        from svos.orchestration.service import SVOSPlatform, PersistenceMode
        platform = SVOSPlatform(root=_ROOT, persistence_mode=PersistenceMode.LOCAL_COMPAT)
        platform.bootstrap()
        target_lc = _UI_STAGE_TO_LC.get(target_stage, "")
        if target_lc:
            platform.audited_transition(
                strategy_id,
                to_stage=target_lc,
                actor="dashboard",
                reason=reason or f"Demoted to {target_stage} via new dashboard",
            )
    except Exception:
        pass

    overlay = _load_overlay()
    ovr_strategies = overlay.setdefault("strategies", {})
    entry = ovr_strategies.get(strategy_id, {})
    entry["status"] = target_stage
    entry["updatedAt"] = now
    entry.setdefault("auditLog", []).append({
        "id": str(uuid.uuid4()),
        "timestamp": now,
        "actor": "Continuous Risk Watcher",
        "action": "stage_demoted",
        "fromStage": current_ui,
        "toStage": target_stage,
        "hash": "",
        "evidenceSummary": reason or f"Demoted to {target_stage}",
        "details": reason,
    })
    ovr_strategies[strategy_id] = entry
    _save_overlay(overlay)

    return get_strategy(strategy_id)
