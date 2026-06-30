from __future__ import annotations

VALIDATOR_RESULT_SCHEMA = {
    "type": "object",
    "required": ["validator_name", "score", "status", "findings", "recommendations"],
    "properties": {
        "validator_name": {"type": "string"},
        "score": {"type": "number"},
        "status": {"type": "string", "enum": ["PASS", "FAIL", "PARTIAL", "WARN"]},
        "findings": {"type": "array"},
        "recommendations": {"type": "array"},
        "metadata": {"type": "object"},
    },
}

VALIDATION_REPORT_SCHEMA = {
    "type": "object",
    "required": [
        "strategy_name",
        "overall_score",
        "overall_status",
        "readiness_decision",
        "validator_results",
        "audit_log",
    ],
    "properties": {
        "strategy_name": {"type": "string"},
        "overall_score": {"type": "number"},
        "overall_status": {
            "type": "string",
            "enum": ["PASS", "FAIL", "PARTIAL", "WARN"],
        },
        "readiness_decision": {
            "type": "string",
            "enum": ["READY_FOR_REPLAY", "REQUIRES_REVISION", "INCOMPLETE", "REJECTED"],
        },
        "validator_results": {"type": "array", "items": VALIDATOR_RESULT_SCHEMA},
        "critical_issues": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "recommendations": {"type": "array"},
        "audit_log": {"type": "array"},
        "summary": {"type": "string"},
        "generated_at": {"type": "string"},
        "source_path": {"type": "string"},
        "document_hash": {"type": "string"},
    },
}

__all__ = ["VALIDATION_REPORT_SCHEMA", "VALIDATOR_RESULT_SCHEMA"]
