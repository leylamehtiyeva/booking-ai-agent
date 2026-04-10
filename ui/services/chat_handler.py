from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any
from app.schemas.fallback_policy import FallbackPolicy
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.logic.conversation_flow import handle_user_message
from app.schemas.query import SearchRequest

from ui.formatters import build_display_answer
from ui.state import append_message, get_search_state, set_search_state


def run_async(coro: Any) -> Any:
    return asyncio.run(coro)


def process_user_message(user_message: str) -> None:
    append_message("user", user_message)

    previous_state = None
    current_state = get_search_state()
    if current_state is not None:
        previous_state = SearchRequest.model_validate(current_state)

    with st.spinner("Thinking..."):
        result = run_async(
            handle_user_message(
                user_message=user_message,
                previous_state=previous_state,
                source="fixtures",
                top_n=5,
                fallback_policy=FallbackPolicy(enabled=True, top_k=5),
                max_items=10,
            )
        )

    assistant_answer = build_display_answer(result)

    debug_data = {
        "parsed_intent": result.get("parsed_intent"),
        "search_request": result.get("search_request"),
        "state_after": result.get("state"),
    }

    append_message("assistant", assistant_answer, debug_data=debug_data)
    set_search_state(result.get("state"))