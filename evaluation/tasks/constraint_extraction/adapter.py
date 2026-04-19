from __future__ import annotations

from typing import Any

from app.logic.intent_router import route_intent_adk_async


async def run_case(user_message: str) -> dict[str, Any]:
    intent = await route_intent_adk_async(user_message)
    return intent.model_dump(mode="json", exclude_none=True)