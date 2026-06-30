"""Port interfaces for the SVOS hexagonal architecture.

Ports are abstract contracts (typing.Protocol) with NO concrete implementations.
They must not import Flask, SQLAlchemy, or any infrastructure adapter.

Available ports:
  research.py   — AuditPort, ReplayPort, BacktestPort, RobustnessPort, VirtualDemoPort
  persistence.py — EvidencePort, TransitionPort
"""

from svos.ports.persistence import EvidencePort, TransitionPort
from svos.ports.research import (
    AuditPort,
    BacktestPort,
    ReplayPort,
    RobustnessPort,
    VirtualDemoPort,
)

__all__ = [
    "AuditPort",
    "ReplayPort",
    "BacktestPort",
    "RobustnessPort",
    "VirtualDemoPort",
    "EvidencePort",
    "TransitionPort",
]
