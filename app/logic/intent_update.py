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
from app.logic.date_normalization import normalize_patch_dates
from app.logic.request_resolution import parse_iso_date
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


def _inherit_month_from_previous_state(
    *,
    previous_state: SearchRequest,
    patch: SearchIntentPatch,
    normalized_check_in: str | None,
    normalized_check_out: str | None,
) -> tuple[str | None, str | None]:
    """
    If the follow-up patch contains new dates but the model likely guessed
    the wrong month, inherit month/year from previous_state.check_in.

    Example:
    previous_state.check_in = 2026-04-20
    patch.set_check_in = 2024-08-08
    patch.set_check_out = 2024-08-16

    Result:
    2026-04-08 / 2026-04-16
    """
    prev_check_in = parse_iso_date(previous_state.check_in)
    if prev_check_in is None:
        return normalized_check_in, normalized_check_out

    raw_check_in = parse_iso_date(patch.set_check_in)
    raw_check_out = parse_iso_date(patch.set_check_out)

    if raw_check_in is None and raw_check_out is None:
        return normalized_check_in, normalized_check_out

    if raw_check_in is not None:
        raw_check_in = raw_check_in.replace(
            year=prev_check_in.year,
            month=prev_check_in.month,
        )

    if raw_check_out is not None:
        raw_check_out = raw_check_out.replace(
            year=prev_check_in.year,
            month=prev_check_in.month,
        )

    return (
        raw_check_in.isoformat() if raw_check_in else None,
        raw_check_out.isoformat() if raw_check_out else None,
    )


async def update_search_state_async(
    previous_state: SearchRequest,
    user_message: str,
) -> SearchRequest:
    patch = await route_intent_update_patch_async(previous_state, user_message)

    normalized_check_in, normalized_check_out = normalize_patch_dates(
        set_check_in=patch.set_check_in,
        set_check_out=patch.set_check_out,
        set_nights=patch.set_nights,
        user_text=user_message,
    )

    if (
        patch.set_check_in is not None or patch.set_check_out is not None
    ) and previous_state.check_in is not None:
        normalized_check_in, normalized_check_out = _inherit_month_from_previous_state(
            previous_state=previous_state,
            patch=patch,
            normalized_check_in=normalized_check_in,
            normalized_check_out=normalized_check_out,
        )

    patch = patch.model_copy(
        update={
            "set_check_in": normalized_check_in,
            "set_check_out": normalized_check_out,
        }
    )

    return apply_intent_patch(previous_state, patch)