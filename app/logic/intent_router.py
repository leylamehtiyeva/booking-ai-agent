from __future__ import annotations

import asyncio
import os
import uuid

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.agents.run_config import RunConfig
from google.genai.types import Content, Part

from app.agents.intent_router_agent import IntentRoute, build_intent_router_agent
from app.schemas.query import SearchRequest


APP_NAME = "booking-ai-agent"
USER_ID = "local-user"


def _ensure_gemini_key() -> None:
    if not os.getenv("GEMINI_API_KEY") and os.getenv("GOOGLE_API_KEY"):
        os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]


async def _route_intent_adk_async(user_text: str) -> IntentRoute:
    _ensure_gemini_key()

    agent = build_intent_router_agent()
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    session_id = f"local-{uuid.uuid4().hex[:8]}"
    # ВАЖНО: create_session async → обязательно await
    await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)

    user_message = Content(role="user", parts=[Part.from_text(text=user_text)])
    run_config = RunConfig(response_modalities=["TEXT"])

    events = []
    async for ev in runner.run_async(
        user_id=USER_ID,
        session_id=session_id,
        new_message=user_message,
        run_config=run_config,
    ):
        events.append(ev)

    parts_text: list[str] = []
    for ev in events:
        content = getattr(ev, "content", None)
        if content and getattr(content, "parts", None):
            for p in content.parts:
                t = getattr(p, "text", None)
                if t:
                    parts_text.append(t)

    final_text = "".join(parts_text).strip()
    if not final_text:
        raise ValueError("ADK returned empty response text")

    def _strip_json_fence(text: str) -> str:
        t = text.strip()
        if t.startswith("```"):
            # убираем первую строку ``` или ```json
            lines = t.splitlines()
            if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
                t = "\n".join(lines[1:-1]).strip()
        return t

    clean = _strip_json_fence(final_text)
    return IntentRoute.model_validate_json(clean)



def route_intent_adk(user_text: str) -> IntentRoute:
    # sync wrapper для твоих smoke-скриптов
    return asyncio.run(_route_intent_adk_async(user_text))


def build_search_request_adk(user_text: str) -> SearchRequest:
    r = route_intent_adk(user_text)
    return SearchRequest(
        user_message=user_text,
        city=r.city,
        must_have_fields=r.must_have_fields,
        nice_to_have_fields=r.nice_to_have_fields,
    )
