from __future__ import annotations

from typing import Any, Dict, Optional

from app.logic.intent_router import build_search_request_adk_async
from app.logic.intent_update import update_search_state_async
from app.logic.request_resolution import resolve_required_search_context
from app.schemas.query import SearchRequest
from app.tools.orchestrate_search_tool import orchestrate_search


async def handle_user_message(
    user_message: str,
    previous_state: Optional[SearchRequest] = None,
    *,
    source: str = "fixtures",
    top_n: int = 5,
    fallback_top_k: int = 5,
    max_items: int = 10,
) -> Dict[str, Any]:
    """
    Main conversational entrypoint.

    - First turn: build a fresh SearchRequest from user text
    - Next turns: update previous SearchRequest via patch-based intent update
    - Always validate required slots before search
    """

    if previous_state is None:
        state = await build_search_request_adk_async(user_message)
    else:
        state = await update_search_state_async(previous_state, user_message)

    resolved = resolve_required_search_context(state)

    if resolved.need_clarification:
        return {
            "need_clarification": True,
            "questions": resolved.questions,
            "state": state.model_dump(mode="json", exclude_none=True),
        }

    result = await orchestrate_search(
        user_text=user_message,
        intent=state.model_dump(mode="json", exclude_none=True),
        top_n=top_n,
        fallback_top_k=fallback_top_k,
        max_items=max_items,
        source=source,
    )

    result["state"] = state.model_dump(mode="json", exclude_none=True)
    return result