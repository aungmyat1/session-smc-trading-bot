#!/usr/bin/env python3
"""System health check — validates all dependencies, config, data, and permissions.

Exit codes:
  0  All checks passed (HEALTHY)
  1  One or more CRITICAL checks failed (UNHEALTHY)
  2  Warnings only (DEGRADED — system functional but sub-optimal)
"""
from __future__ import annotations

import importlib
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)


class CheckLevel(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    level: CheckLevel
    detail: str = ""


@dataclass
class HealthReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def critical_failures(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == CheckStatus.FAIL and c.level == CheckLevel.CRITICAL]

    @property
    def warnings(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == CheckStatus.FAIL and c.level == CheckLevel.WARNING]

    def overall(self) -> str:
        if self.critical_failures:
            return "UNHEALTHY"
        if self.warnings:
            return "DEGRADED"
        return "HEALTHY"


def check_python_version(report: HealthReport) -> None:
    v = sys.version_info
    ok = v >= (3, 11)
    report.checks.append(CheckResult(
        "python_version",
        CheckStatus.PASS if ok else CheckStatus.FAIL,
        CheckLevel.CRITICAL,
        f"Python {v.major}.{v.minor}.{v.micro}" + ("" if ok else " — requires ≥3.11"),
    ))


def check_required_packages(report: HealthReport) -> None:
    required = [
        ("yaml", "PyYAML"),
        ("pytest", "pytest"),
        ("ruff", "ruff"),
        ("mypy", "mypy"),
        ("alembic", "alembic"),
        ("sqlalchemy", "SQLAlchemy"),
    ]
    optional = [
        ("bandit", "bandit"),
        ("pip_audit", "pip-audit"),
        ("black", "black"),
        ("isort", "isort"),
    ]
    for mod, pkg in required:
        try:
            importlib.import_module(mod)
            report.checks.append(CheckResult(f"pkg:{pkg}", CheckStatus.PASS, CheckLevel.CRITICAL, f"{pkg} importable"))
        except ImportError:
            report.checks.append(CheckResult(f"pkg:{pkg}", CheckStatus.FAIL, CheckLevel.CRITICAL, f"{pkg} not installed"))
    for mod, pkg in optional:
        try:
            importlib.import_module(mod)
            report.checks.append(CheckResult(f"pkg:{pkg}", CheckStatus.PASS, CheckLevel.INFO, f"{pkg} available"))
        except ImportError:
            report.checks.append(CheckResult(f"pkg:{pkg}", CheckStatus.SKIP, CheckLevel.WARNING, f"{pkg} not installed — quality gates limited"))


def check_config_files(report: HealthReport) -> None:
    required_configs = [
        "config/testing.yaml",
        "config/approval.yaml",
        "quality/config.yaml",
        "quality/architecture_rules.yaml",
        "quality/import_rules.yaml",
    ]
    for rel in required_configs:
        p = _ROOT / rel
        report.checks.append(CheckResult(
            f"config:{rel}",
            CheckStatus.PASS if p.exists() else CheckStatus.FAIL,
            CheckLevel.CRITICAL,
            str(p),
        ))


def check_agent_modules(report: HealthReport) -> None:
    modules = [
        "agents.testing.agent",
        "agents.quality.agent",
        "agents.approval.agent",
    ]
    for mod in modules:
        try:
            importlib.import_module(mod)
            report.checks.append(CheckResult(f"module:{mod}", CheckStatus.PASS, CheckLevel.CRITICAL, "importable"))
        except ImportError as exc:
            report.checks.append(CheckResult(f"module:{mod}", CheckStatus.FAIL, CheckLevel.CRITICAL, str(exc)))


def check_data_dirs(report: HealthReport) -> None:
    dirs = {
        "data/": CheckLevel.WARNING,
        "reports/": CheckLevel.WARNING,
        "logs/": CheckLevel.INFO,
    }
    for rel, level in dirs.items():
        p = _ROOT / rel
        report.checks.append(CheckResult(
            f"dir:{rel}",
            CheckStatus.PASS if p.exists() else CheckStatus.FAIL,
            level,
            str(p),
        ))


def check_env_vars(report: HealthReport) -> None:
    optional_vars = [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "VANTAGE_DEMO_METAAPI_ID",
    ]
    secret_vars_present = any(os.environ.get(v) for v in optional_vars)
    report.checks.append(CheckResult(
        "env:broker_credentials",
        CheckStatus.PASS if secret_vars_present else CheckStatus.SKIP,
        CheckLevel.INFO,
        "Broker credentials present" if secret_vars_present else "No broker credentials (offline mode only)",
    ))


def check_database_connectivity(report: HealthReport) -> None:
    pg_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if not pg_url:
        report.checks.append(CheckResult(
            "database:connectivity",
            CheckStatus.SKIP,
            CheckLevel.WARNING,
            "DATABASE_URL not set — database features unavailable",
        ))
        return
    try:
        import sqlalchemy as sa
        engine = sa.create_engine(pg_url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
        report.checks.append(CheckResult("database:connectivity", CheckStatus.PASS, CheckLevel.CRITICAL, "PostgreSQL reachable"))
    except Exception as exc:
        report.checks.append(CheckResult("database:connectivity", CheckStatus.FAIL, CheckLevel.CRITICAL, str(exc)[:120]))


def check_ruff_clean(report: HealthReport) -> None:
    proc = subprocess.run(
        ["python", "-m", "ruff", "check", "svos/", "db/", "agents/", "--output-format=concise"],
        cwd=_ROOT, capture_output=True, text=True,
    )
    if proc.returncode == 0:
        report.checks.append(CheckResult("lint:ruff", CheckStatus.PASS, CheckLevel.WARNING, "zero violations"))
    else:
        count = len([line for line in proc.stdout.splitlines() if line.strip() and not line.startswith("Found")])
        report.checks.append(CheckResult("lint:ruff", CheckStatus.FAIL, CheckLevel.WARNING, f"{count} violations found"))


def check_permissions(report: HealthReport) -> None:
    write_targets = ["reports/", "logs/"]
    for rel in write_targets:
        p = _ROOT / rel
        p.mkdir(parents=True, exist_ok=True)
        test_file = p / ".write_test"
        try:
            test_file.write_text("ok")
            test_file.unlink()
            report.checks.append(CheckResult(f"perm:write:{rel}", CheckStatus.PASS, CheckLevel.CRITICAL, "writable"))
        except OSError as exc:
            report.checks.append(CheckResult(f"perm:write:{rel}", CheckStatus.FAIL, CheckLevel.CRITICAL, str(exc)))


def main() -> int:
    report = HealthReport()

    check_python_version(report)
    check_required_packages(report)
    check_config_files(report)
    check_agent_modules(report)
    check_data_dirs(report)
    check_env_vars(report)
    check_database_connectivity(report)
    check_ruff_clean(report)
    check_permissions(report)

    overall = report.overall()
    icon = {"HEALTHY": "✅", "DEGRADED": "⚠️", "UNHEALTHY": "❌"}[overall]

    print(f"\n{icon} System Health: {overall}\n")
    for c in report.checks:
        s_icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭"}[c.status.value]
        lvl = f"[{c.level.value}]" if c.status == CheckStatus.FAIL else ""
        print(f"  {s_icon} {c.name:<40} {lvl} {c.detail}")

    if report.critical_failures:
        print(f"\n❌ {len(report.critical_failures)} critical check(s) failed.")
    if report.warnings:
        print(f"\n⚠️  {len(report.warnings)} warning(s).")

    # Write JSON summary
    out = _ROOT / "reports" / "health_check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "status": overall,
        "checks": [{"name": c.name, "status": c.status.value, "level": c.level.value, "detail": c.detail} for c in report.checks],
    }, indent=2))
    print(f"\nHealth report → {out}")

    return 0 if overall == "HEALTHY" else (2 if overall == "DEGRADED" else 1)


if __name__ == "__main__":
    sys.exit(main())
