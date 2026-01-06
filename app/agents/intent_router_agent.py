from __future__ import annotations
import json
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field as PydField
from google.adk.agents import Agent
from app.schemas.fields import Field
import os
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini

class IntentRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: Optional[str] = None
    must_have_fields: list[Field] = PydField(default_factory=list)
    nice_to_have_fields: list[Field] = PydField(default_factory=list)
    unknown_requests: list[str] = PydField(default_factory=list)


def build_intent_router_agent() -> Agent:
    allowed_fields = [f.name for f in Field]
    schema = IntentRoute.model_json_schema()

    instruction = f"""
You are an intent router for a booking search assistant.

Return ONLY valid JSON matching this schema:
{json.dumps(schema, ensure_ascii=False)}

Rules:
- Choose fields ONLY from allowed_fields: {allowed_fields}
- If a user request does not map confidently to any Field, add it to unknown_requests.
- Do NOT invent fields.
- Output JSON only. No explanations.
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
