"""Immutable content-addressed filesystem artifact storage."""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    sha256: str
    path: Path
    size_bytes: int


class FilesystemArtifactStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def put(self, source: Path | str) -> StoredArtifact:
        source_path = Path(source)
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        digest = hashlib.sha256()
        size = 0
        with source_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        hexdigest = digest.hexdigest()
        destination = self.root / "sha256" / hexdigest[:2] / hexdigest
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.stat().st_size != size:
                raise RuntimeError(f"content-address collision at {destination}")
            return StoredArtifact(hexdigest, destination, size)

        with NamedTemporaryFile(dir=destination.parent, prefix=".artifact-", delete=False) as temporary:
            temp_path = Path(temporary.name)
            with source_path.open("rb") as source_handle:
                shutil.copyfileobj(source_handle, temporary)
            temporary.flush()
            os.fsync(temporary.fileno())
        try:
            os.replace(temp_path, destination)
            destination.chmod(0o444)
        finally:
            temp_path.unlink(missing_ok=True)
        return StoredArtifact(hexdigest, destination, size)

    def verify(self, artifact: StoredArtifact) -> bool:
        if not artifact.path.is_file() or artifact.path.stat().st_size != artifact.size_bytes:
            return False
        digest = hashlib.sha256(artifact.path.read_bytes()).hexdigest()
        return digest == artifact.sha256
