from __future__ import annotations

import argparse
import json
from pathlib import Path

from production import (
    DeploymentImportService,
    ProductionActivationService,
    ProductionDeploymentAgent,
    ProductionObservabilityService,
    ProductionPreflightVerifier,
    ProductionSummaryService,
)


def _root_from_args(args: argparse.Namespace) -> Path:
    if args.root:
        return Path(args.root)
    return Path(__file__).resolve().parents[1]


def production_import_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage a deployment package for production verification.")
    parser.add_argument("--deployment-id", required=True, help="Deployment identifier created by the SVOS deployment service.")
    parser.add_argument("--root", default="", help="Optional repository root override.")
    args = parser.parse_args(argv)

    payload = DeploymentImportService(root=_root_from_args(args)).import_deployment(args.deployment_id)
    print(json.dumps(payload.to_dict(), indent=2, sort_keys=True))
    return 0


def production_import_status_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read the current staged-import status for a deployment.")
    parser.add_argument("--deployment-id", required=True, help="Deployment identifier created by the SVOS deployment service.")
    parser.add_argument("--root", default="", help="Optional repository root override.")
    args = parser.parse_args(argv)

    payload = DeploymentImportService(root=_root_from_args(args)).import_status(args.deployment_id)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def production_preflight_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run production preflight verification against a staged deployment package.")
    parser.add_argument("--deployment-id", required=True, help="Deployment identifier created by the SVOS deployment service.")
    parser.add_argument("--root", default="", help="Optional repository root override.")
    args = parser.parse_args(argv)

    payload = ProductionPreflightVerifier(root=_root_from_args(args)).verify_import(args.deployment_id)
    print(json.dumps(payload.to_dict(), indent=2, sort_keys=True))
    return 0


def production_preflight_status_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read the latest production preflight verification result.")
    parser.add_argument("--deployment-id", required=True, help="Deployment identifier created by the SVOS deployment service.")
    parser.add_argument("--root", default="", help="Optional repository root override.")
    args = parser.parse_args(argv)

    payload = ProductionPreflightVerifier(root=_root_from_args(args)).verification_status(args.deployment_id)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def production_activate_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage a verified deployment for disabled runtime attachment.")
    parser.add_argument("--deployment-id", required=True, help="Deployment identifier created by the SVOS deployment service.")
    parser.add_argument("--root", default="", help="Optional repository root override.")
    parser.add_argument("--request-live", action="store_true", help="Request live activation. This is expected to be blocked.")
    parser.add_argument("--actor", default="cli-operator", help="Actor identity for activation-state audit.")
    args = parser.parse_args(argv)

    payload = ProductionActivationService(root=_root_from_args(args)).stage_runtime(
        args.deployment_id,
        actor=args.actor,
        request_live=bool(args.request_live),
    )
    print(json.dumps(payload.to_dict(), indent=2, sort_keys=True))
    return 0


def production_activate_status_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read the current production activation state.")
    parser.add_argument("--deployment-id", required=True, help="Deployment identifier created by the SVOS deployment service.")
    parser.add_argument("--root", default="", help="Optional repository root override.")
    args = parser.parse_args(argv)

    payload = ProductionActivationService(root=_root_from_args(args)).activation_status(args.deployment_id)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def production_status_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read a consolidated production deployment summary.")
    parser.add_argument("--deployment-id", required=True, help="Deployment identifier created by the SVOS deployment service.")
    parser.add_argument("--root", default="", help="Optional repository root override.")
    args = parser.parse_args(argv)

    payload = ProductionSummaryService(root=_root_from_args(args)).summarize(args.deployment_id)
    print(json.dumps(payload.to_dict(), indent=2, sort_keys=True))
    return 0


def production_deploy_disabled_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import, preflight, and stage a deployment with live trading disabled.")
    parser.add_argument("--deployment-id", required=True)
    parser.add_argument("--root", default="")
    parser.add_argument("--actor", default="deployment-agent")
    args = parser.parse_args(argv)
    payload = ProductionDeploymentAgent(root=_root_from_args(args)).deploy_disabled(args.deployment_id, actor=args.actor)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("overall_status") == "STAGED_DISABLED" else 2


def production_poll_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Poll once for ready disabled deployments.")
    parser.add_argument("--root", default="")
    parser.add_argument("--actor", default="deployment-agent")
    args = parser.parse_args(argv)
    payload = ProductionDeploymentAgent(root=_root_from_args(args)).poll_once(actor=args.actor)
    print(json.dumps({"processed": len(payload), "deployments": payload}, indent=2, sort_keys=True))
    return 0


def production_health_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read production policy and heartbeat health.")
    parser.add_argument("--root", default="")
    parser.add_argument("--heartbeat", action="store_true")
    args = parser.parse_args(argv)
    service = ProductionObservabilityService(root=_root_from_args(args))
    if args.heartbeat:
        service.heartbeat(component="production-cli")
    payload = service.health()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 2
