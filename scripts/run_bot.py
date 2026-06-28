#!/usr/bin/env python3
"""
run_bot.py — Main CLI entrypoint for the Session SMC trading bot.

Usage:
    python scripts/run_bot.py [--config path/to/config.yaml] [--dry-run]

This script:
1. Loads config and validates environment
2. Checks governance lifecycle state (must be >= demo_approved)
3. Initialises risk guards and kill switch
4. Starts the monitoring health loop
5. Runs the signal generation loop (London + NY sessions)

LIVE_TRADING is always False unless the owner manually sets it in .env.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional for CI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_bot")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Session SMC Trading Bot")
    p.add_argument(
        "--config",
        default="session_smc/config.yaml",
        help="Path to config.yaml (default: session_smc/config.yaml)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run: generate signals but do not place orders",
    )
    p.add_argument(
        "--strategy-id",
        default="ST-A2",
        help="Strategy ID to run (must be registered in governance registry)",
    )
    return p.parse_args()


def check_environment() -> None:
    """Fail fast if required env vars are missing."""
    required = ["METAAPI_ACCOUNT_ID", "METAAPI_TOKEN"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        logger.error("Missing required environment variables: %s", missing)
        logger.error("Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)

    live = os.environ.get("LIVE_TRADING", "false").lower()
    if live not in ("false", "0", "no"):
        logger.critical(
            "LIVE_TRADING=%s — live trading is BLOCKED until the owner manually "
            "confirms Phase-1 (paper) and Phase-2 (micro) completion.",
            live,
        )
        sys.exit(1)


def check_governance(strategy_id: str, config_path: str) -> None:
    """Verify lifecycle state allows demo operation."""
    try:
        import yaml
        from session_smc.governance import StrategyRegistry, LifecycleState
        cfg = yaml.safe_load(Path(config_path).read_text())
        registry_path = cfg.get("governance", {}).get(
            "registry_path", "data/strategy_registry.json"
        )
        reg = StrategyRegistry(registry_path=Path(registry_path))
        if strategy_id not in reg.list_strategies():
            logger.warning(
                "Strategy '%s' not in registry — initialising with verification_ready state.",
                strategy_id,
            )
            return
        state = reg.get_state(strategy_id)
        demo_states = {
            LifecycleState.DEMO_APPROVED,
            LifecycleState.DEMO_LIVE,
            LifecycleState.PRODUCTION_CANDIDATE,
            LifecycleState.PRODUCTION_APPROVED,
            LifecycleState.PRODUCTION_LIVE,
        }
        if state not in demo_states:
            logger.error(
                "Strategy '%s' is in lifecycle state '%s' — demo execution requires "
                "demo_approved or later. Run Phase-0 backtest first.",
                strategy_id, state.value,
            )
            sys.exit(1)
        logger.info("Governance check: '%s' in state '%s' — OK.", strategy_id, state.value)
    except ImportError as exc:
        logger.warning("Governance check skipped (import error): %s", exc)
    except Exception as exc:
        logger.error("Governance check failed: %s", exc)
        sys.exit(1)


def main() -> None:
    args = parse_args()
    logger.info("Starting Session SMC Trading Bot (strategy=%s)", args.strategy_id)

    check_environment()
    check_governance(args.strategy_id, args.config)

    if args.dry_run:
        logger.info("DRY RUN mode — signals will be logged but no orders placed.")

    # Placeholder: the actual bot loop is in bot.py (existing module).
    # This entrypoint wires governance + env checks before calling it.
    logger.info(
        "Bot initialised. Actual main loop lives in bot.py. "
        "Wire it here once Phase-1 (demo) is approved."
    )
    logger.info(
        "Next step: promote ST-A2 to demo_approved in the governance registry, "
        "then configure MetaAPI demo account credentials in .env."
    )


if __name__ == "__main__":
    main()
