from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any


def canonical_payload(files: dict[str, bytes]) -> bytes:
    manifest = {name: hashlib.sha256(content).hexdigest() for name, content in sorted(files.items())}
    return json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()


def sign_files(files: dict[str, bytes], key: str | None = None) -> dict[str, Any]:
    secret = key if key is not None else os.getenv("STRATEGY_PACKAGE_SIGNING_KEY", "")
    if not secret:
        raise ValueError("a strategy package signing key is required")
    payload = canonical_payload(files)
    return {
        "scheme": "hmac-sha256",
        "digest_sha256": hashlib.sha256(payload).hexdigest(),
        "signature": hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest(),
        "files": json.loads(payload),
    }


def verify_files(files: dict[str, bytes], envelope: dict[str, Any], key: str | None = None) -> bool:
    secret = key if key is not None else os.getenv("STRATEGY_PACKAGE_SIGNING_KEY", "")
    if not secret or envelope.get("scheme") != "hmac-sha256":
        return False
    payload = canonical_payload(files)
    digest = hashlib.sha256(payload).hexdigest()
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(str(envelope.get("digest_sha256", "")), digest) and hmac.compare_digest(str(envelope.get("signature", "")), expected)
