"""Google Cloud adapters shared by the SVOS publisher and production consumer."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote


class GoogleCloudError(RuntimeError):
    """A cloud operation failed with an operator-actionable message."""


def _authorized_session() -> Any:
    try:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
    except ImportError as exc:  # pragma: no cover
        raise GoogleCloudError("google-auth is required for real Google Cloud operations") from exc
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    return AuthorizedSession(credentials)


def parse_gs_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError(f"invalid GCS URI: {uri}")
    bucket, separator, object_name = uri[5:].partition("/")
    if not bucket or not separator or not object_name:
        raise ValueError(f"invalid GCS URI: {uri}")
    return bucket, object_name


class GCSArtifactAdapter:
    """Upload and fetch immutable objects through the GCS JSON API."""

    def __init__(self, session: Any | None = None) -> None:
        self.session = session or _authorized_session()

    def upload(self, source: Path, uri: str, *, sha256: str) -> None:
        bucket, object_name = parse_gs_uri(uri)
        metadata = {"name": object_name, "metadata": {"sha256": sha256}}
        with source.open("rb") as source_handle:
            response = self.session.post(
                f"https://storage.googleapis.com/upload/storage/v1/b/{quote(bucket, safe='')}/o",
                params={"uploadType": "multipart", "ifGenerationMatch": "0"},
                files={
                    "metadata": (None, json.dumps(metadata), "application/json; charset=UTF-8"),
                    "file": (source.name, source_handle, "application/gzip"),
                },
            )
        if response.status_code == 412:
            existing = self.metadata(uri)
            if existing.get("metadata", {}).get("sha256") == sha256:
                return
            raise GoogleCloudError(f"immutable GCS object already exists with different content: {uri}")
        if not response.ok:
            raise GoogleCloudError(f"GCS upload failed for {uri}: HTTP {response.status_code} {response.text[:300]}")

    def download(self, uri: str, destination: Path, *, expected_sha256: str = "") -> str:
        bucket, object_name = parse_gs_uri(uri)
        response = self.session.get(
            f"https://storage.googleapis.com/download/storage/v1/b/{quote(bucket, safe='')}/o/{quote(object_name, safe='')}",
            params={"alt": "media"},
            stream=True,
        )
        if not response.ok:
            raise GoogleCloudError(f"GCS download failed for {uri}: HTTP {response.status_code} {response.text[:300]}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".part")
        digest = hashlib.sha256()
        try:
            with temporary.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        digest.update(chunk)
                        handle.write(chunk)
            actual = digest.hexdigest()
            if expected_sha256 and actual != expected_sha256:
                raise GoogleCloudError(f"GCS checksum mismatch for {uri}: expected {expected_sha256}, got {actual}")
            temporary.replace(destination)
            return actual
        finally:
            temporary.unlink(missing_ok=True)

    def metadata(self, uri: str) -> dict[str, Any]:
        bucket, object_name = parse_gs_uri(uri)
        response = self.session.get(
            f"https://storage.googleapis.com/storage/v1/b/{quote(bucket, safe='')}/o/{quote(object_name, safe='')}"
        )
        if not response.ok:
            raise GoogleCloudError(f"GCS metadata lookup failed for {uri}: HTTP {response.status_code} {response.text[:300]}")
        payload = response.json()
        return payload if isinstance(payload, dict) else {}


class KMSAsymmetricAdapter:
    """Sign SHA-256 digests and verify them with a Cloud KMS public key."""

    def __init__(self, session: Any | None = None) -> None:
        self.session = session or _authorized_session()

    def sign_digest(self, key_version: str, digest: bytes) -> str:
        response = self.session.post(
            f"https://cloudkms.googleapis.com/v1/{key_version}:asymmetricSign",
            json={"digest": {"sha256": base64.b64encode(digest).decode("ascii")}},
        )
        if not response.ok:
            raise GoogleCloudError(f"KMS signing failed for {key_version}: HTTP {response.status_code} {response.text[:300]}")
        signature = str(response.json().get("signature", ""))
        if not signature:
            raise GoogleCloudError(f"KMS returned no signature for {key_version}")
        return signature

    def verify_digest(self, key_version: str, digest: bytes, signature_b64: str) -> bool:
        response = self.session.get(f"https://cloudkms.googleapis.com/v1/{key_version}/publicKey")
        if not response.ok:
            raise GoogleCloudError(f"KMS public-key lookup failed for {key_version}: HTTP {response.status_code} {response.text[:300]}")
        try:
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import ec, padding, utils

            payload = response.json()
            key = serialization.load_pem_public_key(payload["pem"].encode("ascii"))
            signature = base64.b64decode(signature_b64, validate=True)
            if "EC_SIGN" in str(payload.get("algorithm", "")):
                key.verify(signature, digest, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
            else:
                key.verify(signature, digest, padding.PKCS1v15(), utils.Prehashed(hashes.SHA256()))
            return True
        except InvalidSignature:
            return False
        except (KeyError, TypeError, ValueError) as exc:
            raise GoogleCloudError(f"invalid KMS verification response for {key_version}") from exc


class SecretManagerAdapter:
    """Read a pinned Secret Manager version using Application Default Credentials."""

    def __init__(self, session: Any | None = None) -> None:
        self.session = session or _authorized_session()

    def access(self, version_name: str) -> str:
        if not version_name.startswith("projects/") or "/secrets/" not in version_name or "/versions/" not in version_name:
            raise ValueError("secret reference must be projects/.../secrets/.../versions/...")
        response = self.session.get(f"https://secretmanager.googleapis.com/v1/{version_name}:access")
        if not response.ok:
            raise GoogleCloudError(
                f"Secret Manager access failed for {version_name}: HTTP {response.status_code} {response.text[:300]}"
            )
        try:
            encoded = response.json()["payload"]["data"]
            return base64.b64decode(encoded, validate=True).decode("utf-8")
        except (KeyError, ValueError, UnicodeDecodeError) as exc:
            raise GoogleCloudError(f"invalid Secret Manager response for {version_name}") from exc
