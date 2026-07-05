"""DeepSeek provider adapter.

DeepSeek exposes an OpenAI-compatible chat completion API at
https://api.deepseek.com. We use the official `openai` SDK to avoid hand-rolled
REST and to inherit retries, timeouts, and structured error types.

The adapter is intentionally thin: it translates between SVOS `LLMRequest` /
`LLMResponse` and the SDK call, and it normalizes error reporting. It does not
own retries, caching, or any governance logic. Those concerns belong to the
calling service (`svos.application.refinement`).

Configuration:
- Reads `DEEPSEEK_API_KEY` from the process environment.
- `base_url` defaults to https://api.deepseek.com but can be overridden for
  staging or self-hosted endpoints.
- `model` defaults to `deepseek-chat` (DeepSeek-V3). `deepseek-reasoner`
  (DeepSeek-R1) is also available for reasoning-heavy tasks.
- `timeout` defaults to 60s; reasoning models may need longer.
"""
from __future__ import annotations
import os
from typing import Any

from svos.adapters.llm import LLMRequest, LLMResponse

_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
_DEFAULT_MODEL = "deepseek-chat"
_DEFAULT_TIMEOUT_S = 60.0


class DeepSeekProviderError(RuntimeError):
    """Raised when the DeepSeek API call fails or returns an unusable response."""


class DeepSeekProvider:
    """Concrete LLMProvider implementation backed by the DeepSeek API."""

    name = "deepseek"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = _DEEPSEEK_BASE_URL,
        default_model: str = _DEFAULT_MODEL,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            raise DeepSeekProviderError(
                "DEEPSEEK_API_KEY is not set. Add it to .env or pass api_key explicitly."
            )
        # Imported lazily so the rest of the platform does not require the SDK.
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:  # pragma: no cover - import guard
            raise DeepSeekProviderError(
                "openai SDK is not installed. Run: pip install -r requirements.in"
            ) from exc
        self._client = OpenAI(api_key=key, base_url=base_url, timeout=timeout_s)
        self._default_model = default_model

    def generate(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self._default_model
        try:
            completion = self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": request.system},
                    {"role": "user", "content": request.user},
                ],
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
        except Exception as exc:  # SDK raises many subclasses; treat as a unit.
            raise DeepSeekProviderError(f"DeepSeek call failed: {exc}") from exc

        if not completion.choices:
            raise DeepSeekProviderError("DeepSeek returned no choices.")
        text = completion.choices[0].message.content or ""
        usage = getattr(completion, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0
        raw: dict[str, Any] = {
            "id": getattr(completion, "id", None),
            "model": getattr(completion, "model", model),
        }
        return LLMResponse(
            text=text,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            raw=raw,
        )


__all__ = ["DeepSeekProvider", "DeepSeekProviderError"]
