"""LLM provider adapters for the SVOS research surface.

This package is the only place inside `svos/` that may import a third-party
LLM SDK. All other modules must consume the narrow `LLMProvider` protocol
defined here. Provider implementations (DeepSeek, Gemini, etc.) translate
provider-specific APIs into the common interface.

Governance boundary:
- The LLM adapter is read-only with respect to SVOS state. It never writes
  to the strategy catalog, the lifecycle, or the evidence repository.
- Every call is logged with its prompt hash, response hash, model, and
  timestamp. A new draft produces an evidence artifact but does not
  promote a strategy version.
- Per AGENTS.md §0.2, an AI-suggested spec change is NOT a trial pass. It
  is a draft; the human must accept it as a new version before any
  parameter change is considered evidence.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True, frozen=True)
class LLMRequest:
    """A single LLM call request, normalized across providers."""

    system: str
    user: str
    model: str
    temperature: float = 0.2
    max_tokens: int = 2048


@dataclass(slots=True, frozen=True)
class LLMResponse:
    """A single LLM call response, normalized across providers."""

    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    raw: dict[str, Any]


class LLMProvider(Protocol):
    """Common surface every concrete provider must satisfy."""

    name: str

    def generate(self, request: LLMRequest) -> LLMResponse:
        ...


__all__ = ["LLMRequest", "LLMResponse", "LLMProvider"]
