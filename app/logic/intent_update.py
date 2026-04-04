from __future__ import annotations

import json
import os
import uuid
from typing import Optional

from google.adk.agents.run_config import RunConfig
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

from app.agents.intent_update_agent import build_intent_update_agent
from app.logic.apply_intent_patch import apply_intent_patch
from app.schemas.intent_patch import SearchIntentPatch
from app.schemas.query import SearchRequest

APP_NAME = "booking-ai-agent"
USER_ID = "local-user"


def _ensure_gemini_key() -> None:
    if not os.getenv("GEMINI_API_KEY") and os.getenv("GOOGLE_API_KEY"):
        os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
            t = "\n".join(lines[1:-1]).strip()
    return t


def _build_update_prompt(previous_state: SearchRequest, user_message: str) -> str:
    state_json = json.dumps(
        previous_state.model_dump(mode="json", exclude_none=True),
        ensure_ascii=False,
        indent=2,
    )
    return f"""
Previous structured search state:
{state_json}

New user message:
{user_message}

Return ONLY a JSON patch.
Do NOT return the full state.
Do NOT repeat unchanged fields.
""".strip()


async def route_intent_update_patch_async(
    previous_state: SearchRequest,
    user_message: str,
) -> SearchIntentPatch:
    _ensure_gemini_key()

    agent = build_intent_update_agent()
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    session_id = f"intent-update-{uuid.uuid4().hex[:8]}"
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id,
    )

    prompt = _build_update_prompt(previous_state, user_message)
    msg = Content(role="user", parts=[Part.from_text(text=prompt)])
    cfg = RunConfig(response_modalities=["TEXT"])

    final_text: Optional[str] = None
    async for ev in runner.run_async(
        user_id=USER_ID,
        session_id=session_id,
        new_message=msg,
        run_config=cfg,
    ):
        content = getattr(ev, "content", None)
        if content and getattr(content, "parts", None):
            for p in content.parts:
                t = getattr(p, "text", None)
                if t:
                    final_text = (final_text or "") + t

    if not final_text:
        raise ValueError("Intent update agent returned empty response")

    clean = _strip_json_fence(final_text)
    return SearchIntentPatch.model_validate_json(clean)


async def update_search_state_async(
    previous_state: SearchRequest,
    user_message: str,
) -> SearchRequest:
    patch = await route_intent_update_patch_async(previous_state, user_message)
    return apply_intent_patch(previous_state, patch)