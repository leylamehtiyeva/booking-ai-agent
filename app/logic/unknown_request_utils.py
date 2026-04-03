from __future__ import annotations

from typing import Any


def get_unknown_must_have_requests(intent: dict[str, Any]) -> list[str]:
    """
    MVP version:
    treat all unknown_requests as unresolved must-have-style requests.
    Later we can distinguish must-have vs soft preference more precisely.
    """
    items = intent.get("unknown_requests") or []
    out: list[str] = []

    for item in items:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())

    return out