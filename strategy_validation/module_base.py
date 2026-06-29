from __future__ import annotations

from abc import ABC, abstractmethod

from .models import StrategyDocument, ValidatorResult


class BaseValidator(ABC):
    name = "base"
    version = "1.0"

    @abstractmethod
    def validate(self, document: StrategyDocument) -> ValidatorResult:
        raise NotImplementedError
