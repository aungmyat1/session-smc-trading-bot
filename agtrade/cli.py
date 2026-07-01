from __future__ import annotations

import argparse

from application import (
    audit_main,
    backup_main,
    research_queue_main,
    research_status_main,
    restore_main,
    sample_main,
    svos_main,
    validate_main,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agtrade", description="Canonical operator CLI for the trading platform.")
    subparsers = parser.add_subparsers(dest="domain", required=True)

    research = subparsers.add_parser("research", help="Research queue and status workflows")
    research_subparsers = research.add_subparsers(dest="command", required=True)
    research_queue = research_subparsers.add_parser("queue", help="Run the manifest-driven research queue")
    research_queue.set_defaults(handler=research_queue_main)
    research_status = research_subparsers.add_parser("status", help="Summarize the configured research queue")
    research_status.set_defaults(handler=research_status_main)

    strategy = subparsers.add_parser("strategy", help="Strategy validation and SVOS workflows")
    strategy_subparsers = strategy.add_subparsers(dest="command", required=True)
    strategy_audit = strategy_subparsers.add_parser("audit", help="Run the strategy audit framework")
    strategy_audit.set_defaults(handler=audit_main)
    strategy_validate = strategy_subparsers.add_parser("validate", help="Validate a strategy specification")
    strategy_validate.set_defaults(handler=validate_main)
    strategy_svos = strategy_subparsers.add_parser("svos", help="Run the six-stage SVOS pipeline")
    strategy_svos.set_defaults(handler=svos_main)
    strategy_sample = strategy_subparsers.add_parser("sample", help="Run the deterministic SVOS sample harness")
    strategy_sample.set_defaults(handler=sample_main)

    admin = subparsers.add_parser("admin", help="Administrative control-plane operations")
    admin_subparsers = admin.add_subparsers(dest="command", required=True)
    admin_backup = admin_subparsers.add_parser("backup", help="Create an encrypted control-plane backup")
    admin_backup.set_defaults(handler=backup_main)
    admin_restore = admin_subparsers.add_parser("restore", help="Restore an encrypted control-plane backup")
    admin_restore.set_defaults(handler=restore_main)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args, remaining = parser.parse_known_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 1
    return int(handler(remaining) or 0)
