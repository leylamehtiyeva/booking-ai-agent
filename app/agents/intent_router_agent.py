from __future__ import annotations

import json
import os
from typing import Optional
from app.schemas.property_semantics import OccupancyType, PropertyType
from pydantic import BaseModel, Field as PydanticField
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from app.schemas.fields import Field
from app.schemas.filters import PriceConstraint, SearchFilters
from typing import List
from pydantic import BaseModel, Field as PydanticField, field_validator


class IntentRoute(BaseModel):
    # model_config = ConfigDict(extra="forbid")

    city: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    must_have_fields: List[Field] = PydanticField(default_factory=list)
    nice_to_have_fields: List[Field] = PydanticField(default_factory=list)
    filters: SearchFilters = PydanticField(default_factory=SearchFilters)
    property_types: list[PropertyType] = PydanticField(default_factory=list)
    occupancy_types: list[OccupancyType] = PydanticField(default_factory=list)
    unknown_requests: List[str] = PydanticField(default_factory=list)
    @field_validator(
        "must_have_fields",
        "nice_to_have_fields",
        "property_types",
        "occupancy_types",
        "unknown_requests",
        mode="before",
    )
    @classmethod
    def _none_to_empty_list(cls, v):
        return [] if v is None else v


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

Bathrooms:
- "X bathrooms" → filters.bathrooms_min = X
- "X bathroom" → filters.bathrooms_min = X
- "at least X bathrooms" → filters.bathrooms_min = X
- "more than X bathrooms" → filters.bathrooms_min = X
- "up to X bathrooms" / "at most X bathrooms" / "less than X bathrooms" → filters.bathrooms_max = X
- "between A and B bathrooms" → filters.bathrooms_min = A AND filters.bathrooms_max = B
- Support decimal bathroom counts such as "1.5 bathrooms"


Price:
- Price constraints MUST go into filters.price
- If the user says "per night", "a night", "nightly" → filters.price.scope = "per_night"
- If the user says "total", "for the whole stay", "for all dates", "overall", "in total" → filters.price.scope = "total_stay"
- Put the numeric amount into filters.price.max_amount unless the user clearly asks for a minimum
- Put the currency into filters.price.currency when mentioned
- If the user gives a price amount but does not specify whether it is per night or total, set filters.price.scope = null
- Examples:
  - "under 50 dollars per night" →
    filters.price = {{"min_amount": null, "max_amount": 50, "currency": "USD", "scope": "per_night"}}
  - "up to 500 manat total" →
    filters.price = {{"min_amount": null, "max_amount": 500, "currency": "AZN", "scope": "total_stay"}}
  - "budget at least 100 USD per night" →
    filters.price = {{"min_amount": 100, "max_amount": null, "currency": "USD", "scope": "per_night"}}

PROPERTY TYPE / OCCUPANCY (IMPORTANT):
Some user requests are not amenities and not numeric filters. They describe the class
of property or the occupancy mode.

Use "property_types" for:
- apartment
- hotel
- hostel
- house
- aparthotel
- guesthouse

Examples:
- "I want an apartment" -> property_types = ["apartment"]
- "hotel is okay" -> property_types = ["hotel"]
- "not a hostel" -> add "hostel" to unknown_requests for now if negation cannot be expressed structurally

Use "occupancy_types" for:
- entire_place
- private_room
- shared_room
- hotel_room

Examples:
- "entire place" -> occupancy_types = ["entire_place"]
- "private room" -> occupancy_types = ["private_room"]
- "shared room" / "bed in dorm" -> occupancy_types = ["shared_room"]
- "hotel room" -> occupancy_types = ["hotel_room"]
- For must_have_fields, nice_to_have_fields, property_types, occupancy_types, and unknown_requests:
  always return arrays, never null.
  Use [] when empty.

IMPORTANT:
- Do NOT put apartment / hotel / hostel / house into must_have_fields
- Do NOT put entire place / private room / shared room into must_have_fields
- These belong only in property_types / occupancy_types

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


async def route_intent(user_text: str) -> IntentRoute:
    """
    Convenience wrapper for running the intent router agent and parsing JSON output.
    """
    agent = build_intent_router_agent()

    # TODO: replace this block with your actual ADK runner call pattern
    # depending on how you already run agents elsewhere in the project.
    raise NotImplementedError(
        "route_intent() wrapper is not wired yet. "
        "Use the same ADK runner pattern you already use in your debug script/agent execution flow."
    )