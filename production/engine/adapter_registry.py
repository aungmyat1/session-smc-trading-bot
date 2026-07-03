"""Allowlisted installed strategy runtimes; package archives never supply code."""

from __future__ import annotations

import hashlib
import inspect
import json
import tarfile
from pathlib import Path
from dataclasses import dataclass
from typing import Callable

from production.engine.contracts import RUNTIME_API_VERSION, StrategyRuntime
from shared.strategy_package import validate_canonical_package


@dataclass(frozen=True, slots=True)
class AdapterRegistration:
    adapter_id: str
    version: str
    code_sha256: str
    runtime_api_version: str
    factory: Callable[[dict], StrategyRuntime]


def implementation_hash(factory: Callable[..., object]) -> str:
    try:
        source = inspect.getsource(factory).encode("utf-8")
    except (OSError, TypeError):
        source = f"{factory.__module__}:{factory.__qualname__}".encode()
    return hashlib.sha256(source).hexdigest()


class AdapterRegistry:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], AdapterRegistration] = {}

    def register(self, adapter_id: str, version: str, factory: Callable[[dict], StrategyRuntime], *, code_sha256: str | None = None) -> AdapterRegistration:
        key = (adapter_id.strip(), version.strip())
        if not all(key):
            raise ValueError("adapter id and version are required")
        registration = AdapterRegistration(key[0], key[1], code_sha256 or implementation_hash(factory), RUNTIME_API_VERSION, factory)
        if key in self._items:
            raise ValueError(f"adapter already registered: {key[0]}@{key[1]}")
        self._items[key] = registration
        return registration

    def resolve(self, adapter_id: str, version: str, code_sha256: str, runtime_api_version: str, parameters: dict) -> StrategyRuntime:
        registration = self._items.get((adapter_id, version))
        if registration is None:
            raise PermissionError(f"adapter is not installed or allowlisted: {adapter_id}@{version}")
        if code_sha256 != registration.code_sha256:
            raise PermissionError("installed adapter code hash does not match package")
        if runtime_api_version != registration.runtime_api_version:
            raise PermissionError("adapter runtime API version is unsupported")
        return registration.factory(dict(parameters))

    def load_package(self, package_path: Path | str, *, verifying_public_key: str) -> StrategyRuntime:
        validation = validate_canonical_package(package_path, signing_key=verifying_public_key)
        validation.require_valid()
        with tarfile.open(package_path, "r:gz") as archive:
            stream = archive.extractfile("parameters.json")
            if stream is None:
                raise PermissionError("package parameters are unavailable")
            parameters = json.loads(stream.read())
        manifest = validation.manifest
        return self.resolve(
            str(manifest["adapter_id"]),
            str(manifest["adapter_version"]),
            str(manifest["adapter_code_sha256"]),
            str(manifest["runtime_api_version"]),
            parameters,
        )
