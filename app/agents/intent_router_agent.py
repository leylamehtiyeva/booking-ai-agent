from __future__ import annotations

import json
import os
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field as PydField
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini

from app.schemas.fields import Field


class IntentRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: Optional[str] = None

    # Dates (MVP): ISO strings or null
    check_in: Optional[str] = None   # "YYYY-MM-DD"
    check_out: Optional[str] = None  # "YYYY-MM-DD"

    # IMPORTANT: these are Enum values (Field.value)
    must_have_fields: list[Field] = PydField(default_factory=list)
    nice_to_have_fields: list[Field] = PydField(default_factory=list)

    unknown_requests: list[str] = PydField(default_factory=list)


def build_intent_router_agent() -> Agent:
    # IMPORTANT: Use Field VALUES, not names
    allowed_fields = [f.value for f in Field]
    schema = IntentRoute.model_json_schema()

    instruction = f"""
You are an intent router for a booking search assistant.

Return ONLY VALID JSON matching this schema:
{json.dumps(schema, ensure_ascii=False)}

Rules:
- The user may write in ANY language. Map the meaning to the canonical keys.
- Choose fields ONLY from allowed_fields (canonical keys): {allowed_fields}
- If a user request does not map confidently to any Field, add the original phrase to unknown_requests.
- Do NOT invent fields.
- Dates:
  - If the user provided check-in/check-out dates, output them as ISO strings YYYY-MM-DD.
  - Otherwise set check_in/check_out to null.
- Return ONLY a valid JSON object. No markdown. No code fences.
"""

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY/GOOGLE_API_KEY")

    llm = Gemini(
        model="models/gemini-2.0-flash",
        api_key=api_key,
    )

    return Agent(
        name="intent_router",
        model=llm,
        instruction=instruction,
    )
