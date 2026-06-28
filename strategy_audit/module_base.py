from __future__ import annotations

from abc import ABC, abstractmethod

from .models import AuditContext, AuditResult


class AuditModule(ABC):
    name: str = ""
    mandatory: bool = True

    @abstractmethod
    def audit(self, context: AuditContext) -> AuditResult:
        raise NotImplementedError

