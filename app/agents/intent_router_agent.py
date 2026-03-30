from __future__ import annotations

import json
import os
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field as PydField
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from app.schemas.fields import Field
from app.schemas.filters import PriceConstraint, SearchFilters

class IntentRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: Optional[str] = None

    # Dates (MVP): ISO strings or null
    check_in: Optional[str] = None   # "YYYY-MM-DD"
    check_out: Optional[str] = None  # "YYYY-MM-DD"

    # IMPORTANT: these are Enum values (Field.value)
    must_have_fields: list[Field] = PydField(default_factory=list)
    nice_to_have_fields: list[Field] = PydField(default_factory=list)
    filters: SearchFilters | None = None
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

GENERAL:
- The user may write in ANY language. Map the meaning to canonical keys.
- Return ONLY a valid JSON object. No markdown. No explanations.

CANONICAL FIELDS:
- Choose fields ONLY from allowed_fields (canonical keys): {allowed_fields}
- Put boolean amenities (e.g. kitchen, private_bathroom, wifi) into:
  - must_have_fields
  - nice_to_have_fields

FILTERS (IMPORTANT):
Some user requests are NOT amenities. They are structured constraints.

These MUST go into "filters", not into must_have_fields.

Use the following mapping rules:

Bedrooms:
- "X bedrooms" → filters.bedrooms_min = X
- "at least X bedrooms" → filters.bedrooms_min = X
- "more than X bedrooms" → filters.bedrooms_min = X
- "up to X bedrooms" / "at most X bedrooms" / "less than X bedrooms" → filters.bedrooms_max = X
- "between A and B bedrooms" → filters.bedrooms_min = A AND filters.bedrooms_max = B

Area:
- "X sqm" / "X square meters" → filters.area_sqm_min = X
- "at least X sqm" / "more than X sqm" / "bigger than X square meters" → filters.area_sqm_min = X
- "up to X sqm" / "less than X sqm" / "at most X square meters" → filters.area_sqm_max = X
- "between A and B sqm" → filters.area_sqm_min = A AND filters.area_sqm_max = B

Price:
- Price constraints MUST go into filters.price
- If the user says "per night", "a night", "nightly" → filters.price.scope = "per_night"
- If the user says "total", "for the whole stay", "for all dates", "overall", "in total" → filters.price.scope = "total_stay"
- Put the numeric amount into filters.price.max_amount unless the user clearly asks for a minimum
- Put the currency into filters.price.currency when mentioned
- If the user gives a price amount but does not specify whether it is per night or total, set filters.price.scope = null
- Examples:
  - "under 50 dollars per night" →
    filters.price = {"min_amount": null, "max_amount": 50, "currency": "USD", "scope": "per_night"}
  - "up to 500 manat total" →
    filters.price = {"min_amount": null, "max_amount": 500, "currency": "AZN", "scope": "total_stay"}
  - "budget at least 100 USD per night" →
    filters.price = {"min_amount": 100, "max_amount": null, "currency": "USD", "scope": "per_night"}

IMPORTANT:
- Do NOT put numeric constraints into must_have_fields
- Do NOT leave them in unknown_requests if they can be mapped to filters

UNKNOWN REQUESTS:
- If a request cannot be mapped to either canonical fields or filters, add it to unknown_requests

DATES:
- If the user provided check-in/check-out dates, output them as ISO strings YYYY-MM-DD
- Otherwise set them to null
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
