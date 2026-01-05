# app/logic/fallback_classifier.py
from __future__ import annotations

import asyncio
import uuid
from typing import Optional, Tuple

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.agents.run_config import RunConfig
from google.genai.types import Content, Part

from app.agents.fallback_classifier_agent import build_fallback_classifier_agent
from app.schemas.fields import Field
from app.schemas.listing import ListingRaw
from app.schemas.match import Evidence, EvidenceSource, FieldMatch, Ternary
import os
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-2.0-flash")


APP_NAME = "booking-ai-agent"
USER_ID = "local-user"


def _strip_json_fence(text: str) -> str:
    """Gemini иногда оборачивает JSON в ```json ... ```. Мы это убираем."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
            t = "\n".join(lines[1:-1]).strip()
    return t


def _listing_text(listing: ListingRaw, max_len: int = 4000) -> str:
    """
    Собираем текст, который дадим LLM.
    Важно: ограничиваем длину, чтобы не платить лишнее.
    """
    chunks = []

    if listing.name:
        chunks.append(f"NAME: {listing.name}")

    if listing.property_type:
        chunks.append(f"TYPE: {listing.property_type}")

    # Structured facilities тоже полезны как “текст”
    if listing.facilities:
        chunks.append("FACILITIES:")
        chunks.extend([f"- {x}" for x in listing.facilities[:80]])

    # Rooms facilities
    if listing.rooms:
        chunks.append("ROOMS:")
        for i, r in enumerate(listing.rooms[:5]):
            if r.name:
                chunks.append(f"Room {i+1}: {r.name}")
            for f in (r.facilities or [])[:50]:
                chunks.append(f"- {f}")

    if listing.description:
        chunks.append("DESCRIPTION:")
        chunks.append(listing.description)

    text = "\n".join(chunks).strip()
    return text[:max_len]


async def _classify_field_async(
    field: Field,
    listing_text: str,
    model: str,
) -> Tuple[str, float, str]:
    """
    Возвращает (value, confidence, snippet) из JSON ответа LLM.
    """
    agent = build_fallback_classifier_agent(model=model)
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    session_id = f"fallback-{uuid.uuid4().hex[:8]}"
    await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)

    prompt = (
        f"FIELD: {field.value}\n"
        f"LISTING_TEXT:\n{listing_text}\n"
    )
    msg = Content(role="user", parts=[Part.from_text(text=prompt)])
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

    # лёгкий парсинг без отдельной pydantic-модели
    import json
    data = json.loads(clean)

    return (
        str(data.get("value", "UNCERTAIN")),
        float(data.get("confidence", 0.0)),
        str(data.get("snippet", "")),
    )


def fallback_classify_field(
    listing: ListingRaw,
    field: Field,
    model: str | None = None,
) -> FieldMatch:
    """
    Public sync API: ListingRaw + Field -> FieldMatch.
    """
    text = _listing_text(listing)
    import os

    if model is None:
        model = os.getenv("GEMINI_MODEL")
        if not model:
            raise ValueError("GEMINI_MODEL is not set. Put GEMINI_MODEL=gemini-2.0-flash in .env")



    value_s, conf, snippet = asyncio.run(_classify_field_async(field, text, model=model))

    value_s = value_s.upper().strip()
    if value_s not in {"YES", "NO", "UNCERTAIN"}:
        value_s = "UNCERTAIN"

    value = {
        "YES": Ternary.YES,
        "NO": Ternary.NO,
        "UNCERTAIN": Ternary.UNCERTAIN,
    }[value_s]

    evidence = []
    if snippet:
        evidence.append(
            Evidence(
                source=EvidenceSource.LLM_FALLBACK,
                path="listing.description/facilities",
                snippet=snippet,
            )
        )

    return FieldMatch(
        value=value,
        confidence=max(0.0, min(1.0, conf)),
        evidence=evidence,
    )
