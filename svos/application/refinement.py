"""Strategy Refinement — Phase 1 of the SVOS qualification pipeline.

This module is the ONLY place in the SVOS research surface that may invoke
an LLM provider. Its job is narrow and explicit:

    audited spec + human trigger  →  LLM call  →  draft artifact on disk

A draft is a *suggestion*, not a state change. The service:
  1. Reads the current audited spec for a strategy version.
  2. Builds a prompt with the section skeleton required by the spec format.
  3. Calls the configured LLM provider.
  4. Writes a paired JSON + Markdown artifact under
     `data/svos/reports/refinement/<strategy>/<timestamp>/`.
  5. Records a change_control event of type `LLM_DRAFT_GENERATED`.
  6. NEVER mutates the strategy catalog, lifecycle stage, or evidence.

Per AGENTS.md §0.2, every AI-suggested parameter change must be registered
as a new trial in `docs/VERDICT_LOG.md` before the next backtest is run.
This service emits no such registration; that is the human's responsibility.

Per §Stage-1 of the implementation plan: "AI generates a separate draft
only; failed audit loops back after human acceptance of a new version."
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from svos.adapters.llm import LLMProvider, LLMRequest, LLMResponse
from svos.shared.change_control import build_change_record, write_change_record
from shared.serialization import now_iso, stable_manifest_hash

_DRAFT_SECTION_SKELETON = """\
# Strategy Refinement Draft
# Source version: {version_id}
# Generated: {timestamp}
# Provider: {provider}/{model}
# ⚠ DRAFT ONLY — does not modify strategy state.

## 1. Inferred intent
{{inferred_intent}}

## 2. Proposed rule changes
{{rule_changes}}

## 3. Risk adjustments
{{risk_adjustments}}

## 4. Open questions for human reviewer
{{open_questions}}
"""

_SYSTEM_PROMPT = (
    "You are an assistant helping a quantitative strategist review a trading "
    "strategy specification. You do NOT trade, you do NOT approve anything, "
    "and you do NOT have access to live market data. Your output is a draft "
    "that a human will review. Be specific about which section of the spec "
    "you are proposing to change, and flag any change that would touch a "
    "parameter currently under live evaluation."
)


@dataclass(slots=True, frozen=True)
class RefinementDraft:
    """The result of a single refinement call. Immutable on disk."""

    strategy_id: str
    version_id: str
    provider: str
    model: str
    draft_text: str
    prompt_hash: str
    response_hash: str
    prompt_tokens: int
    completion_tokens: int
    artifact_dir: Path


class RefinementService:
    """Phase-1 Refinement: produce a draft from an audited spec via LLM."""

    def __init__(
        self,
        root: Path | str,
        provider: LLMProvider,
        *,
        max_input_chars: int = 32000,
        include_section_skeleton: bool = True,
        change_log_root: Path | None = None,
    ) -> None:
        self.root = Path(root)
        self._provider = provider
        self._max_input_chars = max_input_chars
        self._include_skeleton = include_section_skeleton
        self._change_log_root = Path(change_log_root) if change_log_root else (self.root / "data" / "svos" / "change_control")
        self.reports_root = self.root / "data" / "svos" / "reports" / "refinement"

    # ------------------------------------------------------------------ public

    def generate_draft(
        self,
        *,
        strategy_id: str,
        version_id: str,
        spec_text: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> RefinementDraft:
        """Build a prompt, call the LLM, persist a paired draft artifact."""
        if not spec_text.strip():
            raise ValueError("spec_text is empty; cannot draft refinement.")
        truncated = spec_text[: self._max_input_chars]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        artifact_dir = self.reports_root / strategy_id / timestamp
        artifact_dir.mkdir(parents=True, exist_ok=True)

        user_prompt = self._build_user_prompt(strategy_id, version_id, truncated)
        request = LLMRequest(
            system=_SYSTEM_PROMPT,
            user=user_prompt,
            model=self._default_model(),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        response: LLMResponse = self._provider.generate(request)
        prompt_hash = hashlib.sha256(user_prompt.encode("utf-8")).hexdigest()[:16]
        response_hash = hashlib.sha256(response.text.encode("utf-8")).hexdigest()[:16]
        draft_text = self._render_draft(
            response.text,
            version_id=version_id,
            timestamp=timestamp,
            provider=self._provider.name,
            model=response.model,
        )

        # Paired JSON + Markdown artifact. JSON is the source of truth.
        manifest = {
            "schema_version": "1.0",
            "report_id": f"refinement-{strategy_id}-{version_id}-{timestamp}",
            "strategy_id": strategy_id,
            "version_id": version_id,
            "provider": self._provider.name,
            "model": response.model,
            "prompt_hash": prompt_hash,
            "response_hash": response_hash,
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "generated_at": now_iso(),
            "spec_chars": len(spec_text),
            "spec_truncated": len(spec_text) > self._max_input_chars,
            "draft": draft_text,
            "raw_response": response.raw,
        }
        manifest["manifest_hash"] = stable_manifest_hash(manifest)
        json_path = artifact_dir / "draft.json"
        md_path = artifact_dir / "draft.md"
        json_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text(draft_text, encoding="utf-8")

        self._change_log_append(
            strategy_id=strategy_id,
            version_id=version_id,
            response=response,
            prompt_hash=prompt_hash,
            response_hash=response_hash,
            report_id=manifest["report_id"],
            artifact_dir=artifact_dir,
        )

        return RefinementDraft(
            strategy_id=strategy_id,
            version_id=version_id,
            provider=self._provider.name,
            model=response.model,
            draft_text=draft_text,
            prompt_hash=prompt_hash,
            response_hash=response_hash,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            artifact_dir=artifact_dir,
        )

    # ----------------------------------------------------------------- helpers

    def _default_model(self) -> str:
        return getattr(self._provider, "_default_model", "deepseek-chat")

    def _build_user_prompt(self, strategy_id: str, version_id: str, spec_text: str) -> str:
        header = (
            f"Strategy: {strategy_id}\n"
            f"Version:  {version_id}\n"
            f"Read the audited spec below and produce a refinement draft.\n"
            f"Fill the four sections (1-4) in the format I provide.\n\n"
        )
        spec_block = f"--- BEGIN SPEC ---\n{spec_text}\n--- END SPEC ---\n"
        if self._include_skeleton:
            return header + _DRAFT_SECTION_SKELETON.format(
                version_id=version_id,
                timestamp="<filled by assistant>",
                provider=self._provider.name,
                model="<filled by assistant>",
            ) + "\n" + spec_block
        return header + spec_block

    def _render_draft(
        self,
        assistant_text: str,
        *,
        version_id: str,
        timestamp: str,
        provider: str,
        model: str,
    ) -> str:
        header = _DRAFT_SECTION_SKELETON.format(
            version_id=version_id,
            timestamp=timestamp,
            provider=provider,
            model=model,
        )
        return header + "\n" + assistant_text.strip() + "\n"

    def _change_log_append(
        self,
        *,
        strategy_id: str,
        version_id: str,
        response: LLMResponse,
        prompt_hash: str,
        response_hash: str,
        report_id: str,
        artifact_dir: Path,
    ) -> None:
        """Emit a `LLM_DRAFT_GENERATED` change record via the SVOS change_control API."""
        summary = (
            f"DeepSeek draft generated for {strategy_id}@{version_id} "
            f"via {self._provider.name}/{response.model}."
        )
        record = build_change_record(
            root=self.root,
            actor="svos.application.refinement",
            change_type="LLM_DRAFT_GENERATED",
            status="DRAFT",
            summary=summary,
            strategy=strategy_id,
            lifecycle_stage="REFINEMENT",
            affected_files=[str(artifact_dir.relative_to(self.root))],
            verification_steps=[
                "Human reviews draft.md under the artifact dir.",
                "If accepted, the human creates a new strategy version and registers a new trial in docs/VERDICT_LOG.md.",
            ],
            notes=[
                f"version_id={version_id}",
                f"provider={self._provider.name}",
                f"model={response.model}",
                f"prompt_hash={prompt_hash}",
                f"response_hash={response_hash}",
                f"report_id={report_id}",
                f"prompt_tokens={response.prompt_tokens}",
                f"completion_tokens={response.completion_tokens}",
            ],
        )
        write_change_record(self.root, record, self._change_log_root)


def load_llm_config(root: Path | str) -> Mapping[str, Any]:
    """Read `config/llm.yaml` relative to the platform root. Returns a dict."""
    path = Path(root) / "config" / "llm.yaml"
    if not path.exists():
        return {"provider": "disabled"}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {"provider": "disabled"}


def build_provider(root: Path | str) -> LLMProvider | None:
    """Construct a provider from `config/llm.yaml`, or None if disabled."""
    cfg = load_llm_config(root)
    name = (cfg.get("provider") or "disabled").lower()
    if name == "disabled":
        return None
    if name != "deepseek":
        raise ValueError(
            f"Unsupported LLM provider: {name!r}. Only 'disabled' and "
            "'deepseek' are wired in this release."
        )
    from svos.adapters.llm.deepseek import DeepSeekProvider  # lazy import

    ds = cfg.get("deepseek") or {}
    return DeepSeekProvider(
        base_url=ds.get("base_url", "https://api.deepseek.com"),
        default_model=ds.get("model", "deepseek-chat"),
        timeout_s=float(ds.get("timeout_s", 60)),
    )


__all__ = [
    "RefinementService",
    "RefinementDraft",
    "load_llm_config",
    "build_provider",
]
