"""
Gemini AI service for new-dashboard endpoints.

Ports the server.ts Gemini logic to Python using google-generativeai SDK.
Returns 503 gracefully if GEMINI_API_KEY is not configured.
"""
from __future__ import annotations

import json
import os
from typing import Any

_GEMINI_MODEL = "gemini-2.0-flash"

_PARSE_SYSTEM = """You are an institutional quantitative trading strategy analyst.
Parse the user's trading idea into a machine-readable specification following
this exact JSON schema. Return ONLY valid JSON — no markdown, no prose.

{
  "name": "Short institutional strategy name",
  "description": "Academic explanation (2-3 sentences)",
  "rules": {
    "assetClass": "Equity|Crypto|Forex",
    "symbol": "e.g. EURUSD, GBPUSD, AAPL, BTC/USD",
    "timeframe": "1D|4H|1H|15M|5M",
    "entryConditions": ["Condition 1", "Condition 2"],
    "exitConditions": ["Exit condition 1"],
    "riskRules": {
      "stopLossPct": 1.0,
      "takeProfitPct": 2.0,
      "maxPositionSizePct": 2.0,
      "dailyLossLimitPct": 3.0
    },
    "parameters": {"key": "value"}
  },
  "audit": {
    "isPassed": true,
    "score": 85,
    "logicalDefects": [
      {
        "id": "defect-0",
        "type": "ambiguity|contradiction|missing_parameter|execution_conflict|undefined_condition",
        "severity": "high|medium|low",
        "title": "Short title",
        "description": "Detailed explanation",
        "affectedRule": "Relevant clause"
      }
    ],
    "recommendations": ["Recommendation 1"]
  }
}"""

_EXPLAIN_SYSTEM = """You are an expert quantitative trading analyst performing
post-trade failure analysis. Given recent losing trades, diagnose the root cause
and provide actionable remediation steps. Return ONLY valid JSON:

{
  "diagnosis": "Root cause summary (2-3 sentences)",
  "primaryFactor": "Main failure mode (e.g. adverse_selection, timing, sizing)",
  "remediation": ["Step 1", "Step 2", "Step 3"],
  "confidenceLevel": "high|medium|low"
}"""


def _get_client() -> Any:
    """Return a Gemini GenerativeModel or raise RuntimeError if unavailable."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    try:
        import google.generativeai as genai  # type: ignore[import]
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(
            model_name=_GEMINI_MODEL,
            generation_config={"response_mime_type": "application/json"},
            system_instruction=None,
        )
    except ImportError:
        raise RuntimeError("google-generativeai not installed. Run: pip install google-generativeai")


def parse_strategy_idea(text: str) -> dict[str, Any]:
    """Parse a free-form trading idea into a structured strategy spec."""
    try:
        import google.generativeai as genai  # type: ignore[import]
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=_GEMINI_MODEL,
            generation_config={"response_mime_type": "application/json"},
        )
        response = model.generate_content(f"{_PARSE_SYSTEM}\n\nTrading idea:\n{text}")
        return json.loads(response.text)
    except RuntimeError:
        raise
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned non-JSON response: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {e}") from e


def explain_failure(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Diagnose recent losing trades and return remediation steps."""
    try:
        import google.generativeai as genai  # type: ignore[import]
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=_GEMINI_MODEL,
            generation_config={"response_mime_type": "application/json"},
        )
        recent = trades[-5:] if len(trades) > 5 else trades
        prompt = f"{_EXPLAIN_SYSTEM}\n\nRecent losing trades (JSON):\n{json.dumps(recent, indent=2)}"
        response = model.generate_content(prompt)
        return json.loads(response.text)
    except RuntimeError:
        raise
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned non-JSON response: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {e}") from e
