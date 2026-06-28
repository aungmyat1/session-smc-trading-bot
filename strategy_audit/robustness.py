from __future__ import annotations

from .module_base import AuditModule
from .models import AuditContext, AuditResult


class ParameterStabilityAuditModule(AuditModule):
    name = "parameter_stability"
    mandatory = True

    def audit(self, context: AuditContext) -> AuditResult:
        grid = context.parameter_grid or {}
        if not grid:
            return AuditResult(self.name, "NOT_VERIFIED", 0.0, recommendation="Provide parameter sweep results")
        best_pf = float(grid.get("best_profit_factor", 0.0) or 0.0)
        runner_up = float(grid.get("runner_up_profit_factor", 0.0) or 0.0)
        spread = abs(best_pf - runner_up)
        stable = best_pf >= 1.0 and spread <= max(0.35, best_pf * 0.25)
        return AuditResult(self.name, "PASS" if stable else "PARTIAL", 100.0 if stable else 55.0, metrics=grid, recommendation="Prefer stable parameter plateaus over fragile peaks")


class SensitivityAuditModule(AuditModule):
    name = "sensitivity"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        if not context.parameter_grid:
            return AuditResult(self.name, "NOT_VERIFIED", 0.0, recommendation="Provide sensitivity grid data")
        return AuditResult(self.name, "PASS", 100.0, metrics={"parameter_sets": len(context.parameter_grid)}, recommendation="Proceed")


class StressTestAuditModule(AuditModule):
    name = "stress_test"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        stress = context.notes.get("stress_test", {})
        if not stress:
            return AuditResult(self.name, "NOT_VERIFIED", 0.0, recommendation="Provide stress-test outputs")
        passed = bool(stress.get("passed", False))
        return AuditResult(self.name, "PASS" if passed else "FAIL", 100.0 if passed else 0.0, metrics=stress, recommendation="Review spread/slippage/latency under stress")


class ScenarioTestingAuditModule(AuditModule):
    name = "scenario_testing"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        scenarios = context.notes.get("scenarios", [])
        if not scenarios:
            return AuditResult(self.name, "NOT_VERIFIED", 0.0, recommendation="Provide scenario-testing evidence")
        failures = [item for item in scenarios if not bool(item.get("passed", True))]
        return AuditResult(self.name, "PASS" if not failures else "PARTIAL", 100.0 if not failures else 60.0, metrics={"scenario_count": len(scenarios), "failures": len(failures)}, recommendation="Cover news, regime, and execution scenarios")

