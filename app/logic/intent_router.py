from __future__ import annotations

import asyncio
import os
import uuid
from typing import Optional

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.agents.run_config import RunConfig
from google.genai.types import Content, Part

from app.agents.intent_router_agent import IntentRoute, build_intent_router_agent
from app.schemas.query import SearchRequest

APP_NAME = "booking-ai-agent"
USER_ID = "local-user"


def _ensure_gemini_key() -> None:
    # ADK/Gemini иногда смотрит в GEMINI_API_KEY
    if not os.getenv("GEMINI_API_KEY") and os.getenv("GOOGLE_API_KEY"):
        os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
            t = "\n".join(lines[1:-1]).strip()
    return t


# ✅ ЭТО единственная "настоящая" async функция, которая делает ADK вызов
async def _route_intent_via_adk(user_text: str) -> IntentRoute:
    _ensure_gemini_key()

    agent = build_intent_router_agent()
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    session_id = f"intent-{uuid.uuid4().hex[:8]}"
    await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)

    msg = Content(role="user", parts=[Part.from_text(text=user_text)])
    cfg = RunConfig(response_modalities=["TEXT"])

    final_text: Optional[str] = None
    async for ev in runner.run_async(user_id=USER_ID, session_id=session_id, new_message=msg, run_config=cfg):
        content = getattr(ev, "content", None)
        if content and getattr(content, "parts", None):
            for p in content.parts:
                t = getattr(p, "text", None)
                if t:
                    final_text = (final_text or "") + t

    if not final_text:
        raise ValueError("ADK returned empty response text")

    clean = _strip_json_fence(final_text)
    return IntentRoute.model_validate_json(clean)


# --- Public APIs ---

async def route_intent_adk_async(user_text: str) -> IntentRoute:
    return await _route_intent_via_adk(user_text)


def route_intent_adk(user_text: str) -> IntentRoute:
    # sync wrapper (использовать только вне event loop)
    return asyncio.run(route_intent_adk_async(user_text))


async def build_search_request_adk_async(user_text: str) -> SearchRequest:
    r = await route_intent_adk_async(user_text)

    return SearchRequest(
        user_message=user_text,
        city=r.city,
        # dates пока нет в IntentRoute → оставляем None
        check_in=None,
        check_out=None,
        # гости/комнаты/валюта → дефолты
        adults=2,
        children=0,
        rooms=1,
        currency="USD",
        budget_max=None,
        must_have_fields=r.must_have_fields,
        nice_to_have_fields=r.nice_to_have_fields,
        forbidden_fields=[],
        min_guest_rating=None,
        property_types=None,
    )



def build_search_request_adk(user_text: str) -> SearchRequest:
    return asyncio.run(build_search_request_adk_async(user_text))
