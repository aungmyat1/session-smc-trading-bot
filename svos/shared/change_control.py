from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import subprocess
from typing import Any

import yaml

from shared.serialization import ensure_parent, now_iso, read_json, stable_manifest_hash


RUNNER_PATTERNS: tuple[str, ...] = (
    "scripts/run_d2_e3_demo.py",
    "scripts/run_strategy_demo.py",
    "scripts/run_st_a2_demo.py",
    "scripts/run_portfolio.py",
    "bot.py",
)

STATE_CANDIDATES: tuple[str, ...] = (
    "logs/strategy_demo_state.json",
    "logs/bot_state.json",
)

LOG_CANDIDATES: tuple[str, ...] = (
    "logs/d2e3_demo.log",
    "logs/strategy_demo.log",
    "logs/portfolio_runner.log",
    "logs/st_a2_demo.log",
    "logs/bot.log",
)


@dataclass(frozen=True)
class ChangeRecord:
    event_id: str
    recorded_at: str
    actor: str
    change_type: str
    status: str
    summary: str
    strategy: str
    lifecycle_stage: str
    affected_files: list[str] = field(default_factory=list)
    verification_steps: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    repo: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, check=False)


def _load_catalog(root: Path) -> dict[str, Any]:
    path = root / "config" / "strategy_catalog.yaml"
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def collect_repo_snapshot(root: Path) -> dict[str, Any]:
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], root)
    commit = _run(["git", "rev-parse", "HEAD"], root)
    status = _run(["git", "status", "--short"], root)
    return {
        "branch": branch.stdout.strip(),
        "commit": commit.stdout.strip(),
        "dirty": bool(status.stdout.strip()),
        "changed_files": [line.strip() for line in status.stdout.splitlines() if line.strip()],
    }


def collect_runtime_snapshot(root: Path) -> dict[str, Any]:
    process_scan = _run(["ps", "-ef"], root)
    process_lines = [line for line in process_scan.stdout.splitlines() if any(pattern in line for pattern in RUNNER_PATTERNS)]
    latest_log: dict[str, Any] = {}
    for rel in LOG_CANDIDATES:
        path = root / rel
        if not path.exists():
            continue
        stat = path.stat()
        if not latest_log or stat.st_mtime > latest_log["mtime_epoch"]:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            latest_log = {
                "path": rel,
                "mtime_epoch": stat.st_mtime,
                "last_line": next((line for line in reversed(lines) if line.strip()), ""),
            }
    latest_state: dict[str, Any] = {}
    for rel in STATE_CANDIDATES:
        payload = read_json(root / rel, {})
        if not isinstance(payload, dict) or not payload:
            continue
        updated_at = str(payload.get("updated_at", ""))
        if not latest_state or updated_at > str(latest_state.get("updated_at", "")):
            latest_state = {"path": rel, **payload}

    runtime_strategy = str(latest_state.get("strategy", "")).strip()
    runtime_status = str(latest_state.get("status", "")).strip()
    return {
        "runner_active": bool(process_lines),
        "runner_processes": process_lines,
        "latest_log": {
            "path": latest_log.get("path", ""),
            "last_line": latest_log.get("last_line", ""),
        },
        "latest_state": latest_state,
        "runtime_strategy": runtime_strategy,
        "runtime_status": runtime_status,
    }


def infer_strategy_context(root: Path, requested_strategy: str = "") -> tuple[str, str]:
    requested = requested_strategy.strip()
    if requested:
        catalog = _load_catalog(root).get("strategies", {})
        manifest = catalog.get(requested, {}) if isinstance(catalog, dict) else {}
        stage = str(manifest.get("svos_stage") or manifest.get("status") or "")
        return requested, stage

    runtime = collect_runtime_snapshot(root)
    if runtime.get("runtime_strategy"):
        strategy = str(runtime["runtime_strategy"])
        catalog = _load_catalog(root).get("strategies", {})
        manifest = catalog.get(strategy, {}) if isinstance(catalog, dict) else {}
        stage = str(manifest.get("svos_stage") or manifest.get("status") or runtime.get("runtime_status") or "")
        return strategy, stage

    catalog_payload = _load_catalog(root)
    current = str(catalog_payload.get("current_strategy") or "").strip()
    if current:
        catalog = catalog_payload.get("strategies", {})
        manifest = catalog.get(current, {}) if isinstance(catalog, dict) else {}
        stage = str(manifest.get("svos_stage") or manifest.get("status") or "")
        return current, stage
    return "", ""


def build_change_record(
    *,
    root: Path,
    actor: str,
    change_type: str,
    status: str,
    summary: str,
    strategy: str = "",
    lifecycle_stage: str = "",
    affected_files: list[str] | None = None,
    verification_steps: list[str] | None = None,
    notes: list[str] | None = None,
) -> ChangeRecord:
    strategy_name, inferred_stage = infer_strategy_context(root, strategy)
    recorded_at = now_iso()
    payload = {
        "recorded_at": recorded_at,
        "actor": actor,
        "change_type": change_type,
        "status": status,
        "summary": summary,
        "strategy": strategy_name,
        "lifecycle_stage": lifecycle_stage or inferred_stage,
    }
    event_id = stable_manifest_hash(payload)
    return ChangeRecord(
        event_id=event_id,
        recorded_at=recorded_at,
        actor=actor,
        change_type=change_type,
        status=status,
        summary=summary,
        strategy=strategy_name,
        lifecycle_stage=lifecycle_stage or inferred_stage,
        affected_files=affected_files or [],
        verification_steps=verification_steps or [],
        notes=notes or [],
        repo=collect_repo_snapshot(root),
        runtime=collect_runtime_snapshot(root),
    )


def render_change_markdown(record: ChangeRecord) -> str:
    lines = [
        f"# Change Record — {record.event_id}",
        "",
        f"- Recorded: `{record.recorded_at}`",
        f"- Actor: `{record.actor}`",
        f"- Type: `{record.change_type}`",
        f"- Status: `{record.status}`",
        f"- Summary: {record.summary}",
        f"- Strategy: `{record.strategy or 'n/a'}`",
        f"- Lifecycle Stage: `{record.lifecycle_stage or 'n/a'}`",
        "",
        "## Repository Snapshot",
        "",
        f"- Branch: `{record.repo.get('branch', '')}`",
        f"- Commit: `{record.repo.get('commit', '')}`",
        f"- Dirty: `{record.repo.get('dirty', False)}`",
    ]
    changed = record.repo.get("changed_files", [])
    lines.append(f"- Changed Files: `{len(changed)}`")
    if changed:
        lines.extend(["", "## Dirty Files", ""])
        lines.extend([f"- `{line}`" for line in changed])

    runtime = record.runtime
    lines.extend(
        [
            "",
            "## Runtime Snapshot",
            "",
            f"- Runner Active: `{runtime.get('runner_active', False)}`",
            f"- Runtime Strategy: `{runtime.get('runtime_strategy', '') or 'n/a'}`",
            f"- Runtime Status: `{runtime.get('runtime_status', '') or 'n/a'}`",
            f"- Latest Log: `{runtime.get('latest_log', {}).get('path', '') or 'n/a'}`",
        ]
    )
    last_line = str(runtime.get("latest_log", {}).get("last_line", "")).strip()
    if last_line:
        lines.append(f"- Latest Log Line: `{last_line}`")

    if record.affected_files:
        lines.extend(["", "## Affected Files", ""])
        lines.extend([f"- `{item}`" for item in record.affected_files])
    if record.verification_steps:
        lines.extend(["", "## Verification", ""])
        lines.extend([f"- {item}" for item in record.verification_steps])
    if record.notes:
        lines.extend(["", "## Notes", ""])
        lines.extend([f"- {item}" for item in record.notes])
    return "\n".join(lines) + "\n"


def write_change_record(root: Path, record: ChangeRecord, output_root: Path) -> tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / f"{record.event_id}.json"
    md_path = output_root / f"{record.event_id}.md"
    ensure_parent(json_path)
    json_path.write_text(json.dumps(record.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_change_markdown(record), encoding="utf-8")

    index_path = output_root / "index.json"
    index_payload = read_json(index_path, {"records": []})
    records = index_payload.get("records", [])
    if not isinstance(records, list):
        records = []
    records = [item for item in records if isinstance(item, dict) and item.get("event_id") != record.event_id]
    records.append(
        {
            "event_id": record.event_id,
            "recorded_at": record.recorded_at,
            "change_type": record.change_type,
            "status": record.status,
            "summary": record.summary,
            "strategy": record.strategy,
            "json": json_path.name,
            "markdown": md_path.name,
        }
    )
    records.sort(key=lambda item: str(item.get("recorded_at", "")), reverse=True)
    index_path.write_text(json.dumps({"records": records}, indent=2, sort_keys=True), encoding="utf-8")
    return json_path, md_path
