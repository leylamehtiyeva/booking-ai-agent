# scripts/smoke_adk_orchestrator_agent.py
from __future__ import annotations

import asyncio
import uuid

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agents.orchestrator_agent import build_orchestrator_agent


APP_NAME = "booking-ai-agent"
USER_ID = "local-user"


async def _run_once(text: str) -> str | None:
    agent = build_orchestrator_agent(model_name="models/gemini-2.0-flash")
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    session_id = f"orch-{uuid.uuid4().hex[:8]}"
    await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)

    msg = types.Content(role="user", parts=[types.Part(text=text)])

    final_text = None

    async for ev in runner.run_async(user_id=USER_ID, session_id=session_id, new_message=msg):
        if ev.is_final_response():
            texts = []
            for p in getattr(ev.content, "parts", []) or []:
                t = getattr(p, "text", None)
                if t:
                    texts.append(t)
            final_text = "\n".join(texts) if texts else None

    print(final_text)
    return final_text


def main() -> None:
    text = (
        """Хочу квартиру в Токио с 12 февраля 2027 года по 14 февраля 2027 года
        """
    )
    out = asyncio.run(_run_once(text))
    assert out is not None


if __name__ == "__main__":
    main()
