"""Canonical System 2 runtime lifecycle authority.

This module owns package preflight, single-process ownership, component
selection, lifecycle state, and runtime events. It does not implement strategy,
risk calculations, broker behavior, or order execution.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from shared.configuration.symbols import validate_symbol
from shared.serialization import append_jsonl, now_iso, read_json, write_json
from shared.strategy_package import CanonicalPackageValidation, validate_canonical_package

ACTIVE_RUNTIME_MODULES = (
    "production.engine.runtime",
    "execution.control_plane",
    "execution.execution_state",
    "execution.governance_guard",
    "execution.market_data",
    "execution.mt5_connector",
    "execution.order_manager",
    "execution.position_sizer",
    "execution.risk_manager",
    "execution.trade_manager",
)

SUPPORTED_BROKER_ADAPTERS = frozenset({"vantage-demo"})
SUPPORTED_RISK_ENFORCERS = frozenset({"demo-risk-firewall"})
LEGACY_RUNTIME_ENTRYPOINTS = (
    "bot.py",
    "scripts/run_st_a2_demo.py",
    "scripts/run_d2_e3_demo.py",
)


class RuntimeState(StrEnum):
    STOPPED = "STOPPED"
    VALIDATING_PACKAGE = "VALIDATING_PACKAGE"
    READY = "READY"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class RuntimeOwnershipError(RuntimeError):
    """Raised when another canonical runtime owner holds the lock."""


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    owner_id: str
    package_path: str
    package_id: str
    package_sha256: str
    strategy_id: str
    strategy_version: str
    symbols: tuple[str, ...]
    broker_adapter: str
    risk_enforcer: str


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    owner_id: str
    state: str
    package_path: str
    package_id: str
    package_sha256: str
    strategy_id: str
    strategy_version: str
    symbols: tuple[str, ...]
    broker_adapter: str
    risk_enforcer: str
    reason: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["symbols"] = list(self.symbols)
        return payload


RuntimeFactory = Callable[[RuntimeContext], Awaitable[None]]
RuntimeEventSink = Callable[[dict[str, Any]], None]

if TYPE_CHECKING:
    from production.engine.execution_pipeline import CanonicalExecutionPipeline, PipelineWorkload

PipelineFactory = Callable[[RuntimeContext], "CanonicalExecutionPipeline"]


class RuntimeAuthority:
    """Single authoritative lifecycle owner for the thin execution layer."""

    def __init__(
        self,
        *,
        root: Path | str,
        package_path: Path | str,
        verifying_public_key: str,
        expected_strategy_id: str | None = None,
        broker_adapter: str = "vantage-demo",
        risk_enforcer: str = "demo-risk-firewall",
        event_sink: RuntimeEventSink | None = None,
    ) -> None:
        self.root = Path(root)
        self.package_path = Path(package_path)
        self.verifying_public_key = verifying_public_key
        self.expected_strategy_id = expected_strategy_id
        self.broker_adapter = broker_adapter
        self.risk_enforcer = risk_enforcer
        self.event_sink = event_sink
        self.owner_id = str(uuid4())
        self.state_root = self.root / "data" / "production" / "runtime"
        self.lock_path = self.state_root / "runtime-owner.lock"
        self.state_path = self.state_root / "runtime-state.json"
        self.events_path = self.state_root / "runtime-events.jsonl"
        self._owns_lock = False
        self._validation: CanonicalPackageValidation | None = None
        self._snapshot = RuntimeSnapshot(
            self.owner_id,
            RuntimeState.STOPPED,
            str(self.package_path),
            "",
            "",
            "",
            "",
            (),
            broker_adapter,
            risk_enforcer,
            "not started",
            now_iso(),
        )

    def snapshot(self) -> RuntimeSnapshot:
        return self._snapshot

    def persisted_state(self) -> dict[str, Any]:
        return read_json(self.state_path, self._snapshot.to_dict())

    async def run(self, runtime_factory: RuntimeFactory) -> None:
        """Validate, acquire ownership, run, and safely release one runtime."""

        try:
            self._acquire_ownership()
            validation = self._validate_startup()
            self._validation = validation
            context = self._context(validation)
            self._transition(RuntimeState.READY, "package and runtime selections verified", context)
            self._transition(RuntimeState.STARTING, "runtime adapter starting", context)
            self._transition(RuntimeState.RUNNING, "runtime authority active", context)
            await runtime_factory(context)
        except RuntimeOwnershipError:
            raise
        except (PermissionError, ValueError) as exc:
            self._transition(RuntimeState.REJECTED, str(exc))
            raise
        except asyncio.CancelledError:
            self._transition(RuntimeState.STOPPING, "runtime cancellation requested")
            raise
        except Exception as exc:
            self._transition(RuntimeState.FAILED, str(exc))
            raise
        finally:
            if self._snapshot.state in {RuntimeState.RUNNING, RuntimeState.STARTING, RuntimeState.READY}:
                self._transition(RuntimeState.STOPPING, "runtime adapter stopped")
            self._release_ownership()
            if self._snapshot.state not in {RuntimeState.REJECTED, RuntimeState.FAILED}:
                self._transition(RuntimeState.STOPPED, "safe shutdown complete")

    async def run_pipeline(self, pipeline_factory: PipelineFactory, workload: "PipelineWorkload") -> None:
        """Validate the package, then construct and invoke the canonical pipeline."""

        async def _owned_pipeline(context: RuntimeContext) -> None:
            pipeline = pipeline_factory(context)
            await pipeline.run(context, workload)

        await self.run(_owned_pipeline)

    def _validate_startup(self) -> CanonicalPackageValidation:
        self._transition(RuntimeState.VALIDATING_PACKAGE, "validating canonical strategy package")
        if self.broker_adapter not in SUPPORTED_BROKER_ADAPTERS:
            raise ValueError(f"unsupported broker adapter selection: {self.broker_adapter}")
        if self.risk_enforcer not in SUPPORTED_RISK_ENFORCERS:
            raise ValueError(f"unsupported risk enforcer selection: {self.risk_enforcer}")
        revocations = read_json(self.root / "data" / "production" / "revoked_packages.json", {})
        revoked_ids = set(revocations.get("package_ids", [])) if isinstance(revocations, dict) else set()
        validation = validate_canonical_package(
            self.package_path,
            signing_key=self.verifying_public_key,
            expected_strategy_id=self.expected_strategy_id,
            revoked_package_ids=revoked_ids,
        )
        validation.require_valid()
        symbols = tuple(str(value) for value in validation.manifest.get("symbols", []))
        if not symbols:
            raise PermissionError("canonical runtime package symbols are missing")
        for symbol in symbols:
            result = validate_symbol(symbol, scope="execution")
            if not result.valid:
                raise PermissionError("; ".join(result.errors))
        return validation

    def _context(self, validation: CanonicalPackageValidation) -> RuntimeContext:
        manifest = validation.manifest
        return RuntimeContext(
            owner_id=self.owner_id,
            package_path=validation.archive_path,
            package_id=validation.package_id,
            package_sha256=validation.archive_sha256,
            strategy_id=str(manifest.get("strategy_id", "")),
            strategy_version=str(manifest.get("strategy_version", "")),
            symbols=tuple(str(value) for value in manifest.get("symbols", [])),
            broker_adapter=self.broker_adapter,
            risk_enforcer=self.risk_enforcer,
        )

    def _acquire_ownership(self) -> None:
        self.state_root.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            current = self.lock_path.read_text(encoding="utf-8", errors="replace") if self.lock_path.exists() else "unknown"
            raise RuntimeOwnershipError(f"canonical runtime owner already active: {current}") from exc
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"owner_id": self.owner_id, "pid": os.getpid(), "acquired_at": now_iso()}, handle, sort_keys=True)
            handle.write("\n")
        self._owns_lock = True
        self._emit("runtime_ownership_acquired")

    def _release_ownership(self) -> None:
        if not self._owns_lock:
            return
        try:
            lock = json.loads(self.lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            lock = {}
        if lock.get("owner_id") == self.owner_id:
            self.lock_path.unlink(missing_ok=True)
        self._owns_lock = False
        self._emit("runtime_ownership_released")

    def _transition(self, state: RuntimeState, reason: str, context: RuntimeContext | None = None) -> None:
        current = context or (self._context(self._validation) if self._validation is not None else None)
        self._snapshot = RuntimeSnapshot(
            owner_id=self.owner_id,
            state=state,
            package_path=str(self.package_path),
            package_id=current.package_id if current else "",
            package_sha256=current.package_sha256 if current else "",
            strategy_id=current.strategy_id if current else (self.expected_strategy_id or ""),
            strategy_version=current.strategy_version if current else "",
            symbols=current.symbols if current else (),
            broker_adapter=self.broker_adapter,
            risk_enforcer=self.risk_enforcer,
            reason=reason,
            updated_at=now_iso(),
        )
        write_json(self.state_path, self._snapshot.to_dict())
        self._emit("runtime_state_changed", state=state, reason=reason)

    def _emit(self, event: str, **fields: Any) -> None:
        payload = {"event": event, "owner_id": self.owner_id, "timestamp": now_iso(), **fields}
        append_jsonl(self.events_path, payload)
        if self.event_sink is not None:
            self.event_sink(payload)


def runtime_module_inventory() -> tuple[str, ...]:
    return ACTIVE_RUNTIME_MODULES
