from __future__ import annotations

from typing import Any


def get_unknown_must_have_requests(intent: dict[str, Any]) -> list[str]:
    """
    Legacy compatibility helper.

    This utility reads the old unknown_requests field and normalizes it into a
    list of strings. It does NOT define user meaning and must not be used as the
    semantic source of truth in new logic.

    In the constraint-centric architecture, unresolved user meaning should be
    read from constraints instead.
    """
    items = intent.get("unknown_requests") or []
    out: list[str] = []

    for item in items:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())

    return out