from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from infrastructure.google_cloud import GCSArtifactAdapter, GoogleCloudError, SecretManagerAdapter, parse_gs_uri


class _Response:
    ok = True
    status_code = 200
    text = ""

    def __init__(self, content: bytes = b"", payload: dict | None = None) -> None:
        self.content = content
        self._payload = payload or {}

    def iter_content(self, chunk_size: int):
        yield self.content

    def json(self):
        return self._payload


class _Session:
    def __init__(self, response: _Response) -> None:
        self.response = response

    def get(self, *args, **kwargs):
        return self.response


def test_parse_gs_uri_requires_bucket_and_object() -> None:
    assert parse_gs_uri("gs://bucket/path/archive.tgz") == ("bucket", "path/archive.tgz")
    with pytest.raises(ValueError):
        parse_gs_uri("gs://bucket")


def test_gcs_download_verifies_sha256_before_atomic_replace(tmp_path: Path) -> None:
    content = b"immutable artifact"
    destination = tmp_path / "package.tar.gz"
    digest = GCSArtifactAdapter(_Session(_Response(content))).download(
        "gs://bucket/package.tar.gz", destination, expected_sha256=hashlib.sha256(content).hexdigest()
    )
    assert destination.read_bytes() == content
    assert digest == hashlib.sha256(content).hexdigest()


def test_gcs_download_rejects_checksum_mismatch(tmp_path: Path) -> None:
    destination = tmp_path / "package.tar.gz"
    with pytest.raises(GoogleCloudError, match="checksum mismatch"):
        GCSArtifactAdapter(_Session(_Response(b"wrong"))).download(
            "gs://bucket/package.tar.gz", destination, expected_sha256="0" * 64
        )
    assert not destination.exists()


def test_secret_manager_decodes_pinned_secret_version() -> None:
    session = _Session(_Response(payload={"payload": {"data": "c2VjcmV0LXZhbHVl"}}))

    value = SecretManagerAdapter(session).access("projects/demo/secrets/broker/versions/1")

    assert value == "secret-value"


def test_secret_manager_rejects_unpinned_reference() -> None:
    with pytest.raises(ValueError, match="versions"):
        SecretManagerAdapter(_Session(_Response())).access("projects/demo/secrets/broker")
