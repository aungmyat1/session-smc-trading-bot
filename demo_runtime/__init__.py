"""Demo-only runtime readiness checks; no live trading capability lives here."""

from demo_runtime.demo_health_check import DemoReadinessResult, evaluate_demo_readiness

__all__ = ["DemoReadinessResult", "evaluate_demo_readiness"]
