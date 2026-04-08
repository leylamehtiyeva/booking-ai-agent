from __future__ import annotations

from typing import Any, Dict, Optional

from app.logic.intent_router import build_search_request_adk_async
from app.logic.intent_update import update_search_state_async
from app.logic.request_resolution import resolve_required_search_context
from app.logic.conversation_router import route_conversation_async
from app.logic.listing_signals import collect_listing_signals
from app.logic.unknown_field_evidence_search import search_unknown_must_have_evidence
from app.schemas.query import SearchRequest
from app.tools.orchestrate_search_tool import orchestrate_search


async def _answer_listing_question(
    *,
    user_message: str,
    shown_listing: dict[str, Any] | None,
    previous_state: SearchRequest | None,
    route_debug: dict[str, Any] | None = None,
) -> Dict[str, Any]:
    previous_state_json = (
        previous_state.model_dump(mode="json", exclude_none=True)
        if previous_state
        else None
    )

    if shown_listing is None:
        return {
            "need_clarification": False,
            "response_type": "listing_question",
            "answer": "I need a specific shown listing to answer that question.",
            "state": previous_state_json,
            "parsed_intent": {
                "router": route_debug,
                "user_message": user_message,
            },
            "search_request": previous_state_json,
        }

    signals = collect_listing_signals(shown_listing)
    evidence_result = await search_unknown_must_have_evidence(
        query_text=user_message,
        listing_signals=signals,
    )

    return {
        "need_clarification": False,
        "response_type": "listing_question",
        "answer": evidence_result.reason,
        "listing_question_result": evidence_result.model_dump(mode="json"),
        "state": previous_state_json,
        "parsed_intent": {
            "router": route_debug,
            "user_message": user_message,
            "listing_question_result": evidence_result.model_dump(mode="json"),
        },
        "search_request": previous_state_json,
    }


async def handle_user_message(
    user_message: str,
    previous_state: Optional[SearchRequest] = None,
    *,
    source: str = "fixtures",
    top_n: int = 5,
    fallback_top_k: int = 5,
    max_items: int = 10,
    shown_listing: dict[str, Any] | None = None,
    latest_result_context: dict[str, Any] | None = None,
) -> Dict[str, Any]:
    route_debug: dict[str, Any] | None = None
    previous_state_json: dict[str, Any] | None = (
        previous_state.model_dump(mode="json", exclude_none=True)
        if previous_state is not None
        else None
    )

    if previous_state is None:
        state = await build_search_request_adk_async(user_message)
        route_debug = {"route": "initial_search"}
        parsed_intent_debug = {
            "router": route_debug,
            "user_message": user_message,
            "previous_state": None,
        }
    else:
        route = await route_conversation_async(
            user_message=user_message,
            previous_state=previous_state,
            latest_result_context=latest_result_context,
        )

        route_debug = route.model_dump(exclude_none=True)

        print("\n=== CONVERSATION ROUTE ===")
        print(route_debug)

        if route.route == "listing_question":
            return await _answer_listing_question(
                user_message=user_message,
                shown_listing=shown_listing,
                previous_state=previous_state,
                route_debug=route_debug,
            )

        if route.route == "new_search":
            state = await build_search_request_adk_async(user_message)
        elif route.route == "search_update":
            state = await update_search_state_async(previous_state, user_message)
        else:
            return {
                "need_clarification": False,
                "response_type": "other",
                "answer": "I can help with a new search, updating the current search, or answering questions about a shown listing.",
                "state": previous_state_json,
                "parsed_intent": {
                    "router": route_debug,
                    "user_message": user_message,
                    "previous_state": previous_state_json,
                },
                "search_request": previous_state_json,
            }

        parsed_intent_debug = {
            "router": route_debug,
            "user_message": user_message,
            "previous_state": previous_state_json,
        }

    state_json = state.model_dump(mode="json", exclude_none=True)

    print("\n=== UPDATED STATE ===")
    print(state_json)

    resolved = resolve_required_search_context(state)

    if resolved.need_clarification:
        return {
            "need_clarification": True,
            "questions": resolved.questions,
            "state": state_json,
            "parsed_intent": parsed_intent_debug,
            "search_request": state_json,
        }

    result = await orchestrate_search(
        user_text=user_message,
        intent=state_json,
        top_n=top_n,
        fallback_top_k=fallback_top_k,
        max_items=max_items,
        source=source,
    )

    result["state"] = state_json
    result["parsed_intent"] = parsed_intent_debug
    result["search_request"] = state_json

    return result