"""Production runtime boundary.

This package root marks the future live/demo execution engine ownership surface.
Stage 2 intentionally keeps runtime behavior in existing modules while adding a
stable import boundary that tests can enforce.
"""

from production.importer import DeploymentImportService, ImportedDeploymentPackage
from production.activation import ActivationRecord, ProductionActivationService
from production.summary import ProductionDeploymentSummary, ProductionSummaryService
from production.verifier import PreflightVerificationResult, ProductionPreflightVerifier
from production.deployment_agent import ProductionDeploymentAgent
from production.observability import ProductionObservabilityService

__all__ = [
    "ActivationRecord",
    "DeploymentImportService",
    "ImportedDeploymentPackage",
    "PreflightVerificationResult",
    "ProductionDeploymentSummary",
    "ProductionActivationService",
    "ProductionDeploymentAgent",
    "ProductionObservabilityService",
    "ProductionSummaryService",
    "ProductionPreflightVerifier",
]
