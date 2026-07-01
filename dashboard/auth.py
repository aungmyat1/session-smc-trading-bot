from __future__ import annotations

import hmac
import os
from functools import wraps

from flask import jsonify, request


def require_operator(app, *allowed_roles: str):
    """Require bearer authentication, a stable actor, and an allowed role."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            configured = str(app.config.get("SVOS_OPERATOR_TOKEN") or os.getenv("SVOS_OPERATOR_TOKEN", ""))
            supplied = request.headers.get("Authorization", "")
            actor = request.headers.get("X-SVOS-Actor", "").strip()
            role = request.headers.get("X-SVOS-Role", "").strip()
            expected = f"Bearer {configured}" if configured else ""
            if not configured:
                return jsonify({"error": "Operator authentication is not configured"}), 503
            if not hmac.compare_digest(supplied, expected):
                return jsonify({"error": "Unauthorized"}), 401
            if not actor:
                return jsonify({"error": "Missing immutable operator identity"}), 401
            if role not in allowed_roles:
                return jsonify({"error": "Forbidden", "required_roles": list(allowed_roles)}), 403
            request.environ["svos.actor"] = actor
            request.environ["svos.role"] = role
            return view(*args, **kwargs)

        return wrapped

    return decorator
