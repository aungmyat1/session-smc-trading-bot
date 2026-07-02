from __future__ import annotations

from typing import Any


async def broker_connection_ok(broker: Any) -> bool:
    try:
        result = broker.connect()
        if hasattr(result, "__await__"):
            await result
        return bool(getattr(broker, "is_connected", True))
    except Exception:
        return False
