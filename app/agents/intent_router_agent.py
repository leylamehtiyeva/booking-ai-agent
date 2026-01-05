from __future__ import annotations
import json
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field as PydField
from google.adk.agents import Agent
from app.schemas.fields import Field

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
    return Agent(
        name="intent_router",
        model="gemini-2.0-flash",
        instruction=instruction,
    )
