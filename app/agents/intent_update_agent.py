from __future__ import annotations

import json
import os

from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini

from app.schemas.intent_patch import SearchIntentPatch


def build_intent_update_agent() -> Agent:
    schema = SearchIntentPatch.model_json_schema()

    instruction = f"""
You update an existing structured booking search request.

Return ONLY valid JSON matching this schema:
{json.dumps(schema, ensure_ascii=False)}

IMPORTANT:
- Return ONLY a PATCH, not the full state
- Only include changes caused by the new user message
- Do NOT repeat unchanged values from previous state
- The current structured state is the source of truth
- Do NOT reconstruct the full request from memory or from earlier wording
- Do NOT revert existing fields unless the user explicitly changes or removes them
- If the user asks for something unsupported by the schema, return an empty patch
- The user may write in any language
- Use empty arrays where nothing should be added/removed

SEMANTICS:
- "also", "add", "with too", "include" -> add_*
- "remove", "not needed", "no longer important" -> remove_* or clear_*
- "instead", "actually", "not X but Y", "change to" -> set_*
- Use clear_city / clear_dates / clear_filters only when the user explicitly removes the whole slot
- If the user changes only one slot, update only that slot
- If the message is ambiguous or unsupported, return an empty patch

SOURCE OF TRUTH:
- The provided previous structured state is the only source of truth for the current search
- Preserve all existing values unless the new user message explicitly changes them
- Never re-derive city, dates, guests, or other slots from older wording
- Never return values just because they existed before; only return actual changes

DATES:
- If user gives one date only, set_check_in to that date and set_nights = 1
- If user says "from X for N nights", set_check_in = X and set_nights = N
- If user gives both dates, set_check_in and set_check_out
- Do not invent dates

UNKNOWN REQUESTS:
- If the user asks for a must-have constraint that cannot be mapped to canonical fields, filters, property_types, or occupancy_types, add it to add_unknown_requests
- Keep the phrase short but meaningful
- Do NOT convert "2 beds" into bedrooms_min
- Do NOT convert unsupported bed configuration requests into must_have_fields
- Examples of unsupported but meaningful requests:
  - "2 beds"
  - "quiet neighborhood"
  - "sea view balcony"

FILTERS:
- For filters, return only the changed filter fields
- Do NOT rebuild the entire filters object if only one field changed
- Example: if user says "now at least 3 bedrooms", only set bedrooms_min = 3

PROPERTY TYPES:
- apartment / hotel / hostel / house / aparthotel / guesthouse


GUESTS AND ROOMS:
- If the user changes the number of people, update guest counts
- "for 3 people" -> set_adults = 3, set_children = 0
- "for 4 adults" -> set_adults = 4
- "2 adults and 1 child" -> set_adults = 2, set_children = 1
- "2 adults and 2 children" -> set_adults = 2, set_children = 2
- "1 child" -> set_children = 1
- "3 rooms" -> set_rooms = 3
- If the user only says total people and does not mention children, treat them as adults
- Only update the fields explicitly changed by the user

OCCUPANCY TYPES:
- entire_place / private_room / shared_room / hotel_room

EXAMPLES:

Previous state has city=Baku.
User: "actually Tbilisi"
Return:
{{"set_city":"Tbilisi"}}

User: "also I want a kettle"
Return:
{{"add_must_have_fields":["kettle"]}}

User: "kitchen is no longer required"
Return:
{{"remove_must_have_fields":["kitchen"]}}

User: "now at least 3 bedrooms"
Return:
{{"set_filters":{{"bedrooms_min":3}}}}

User: "хочу чтобы были 2 кровати"
Return:
{{"add_unknown_requests":["2 beds"]}}

User: "I need satellite TV"
Return:
{{"add_unknown_requests":["satellite TV"]}}

User: "for 3 people"
Return:
{{"set_adults":3,"set_children":0}}

Previous state has city=Baku, check_in=2026-04-19, check_out=2026-04-23, adults=2.
User: "change city to Tbilisi"
Return:
{{"set_city":"Tbilisi"}}

Previous state has city=Baku, check_in=2026-04-19, check_out=2026-04-23, adults=2.
User: "на 3 человек"
Return:
{{"set_adults":3,"set_children":0}}

Previous state has city=Baku, check_in=2026-04-19, check_out=2026-04-23, adults=2.
User: "хочу чтобы были 2 кровати"
Return:
{{}}

Previous state has city=Baku, check_in=2026-04-19, check_out=2026-04-23, adults=2.
User: "actually city does not matter"
Return:
{{"clear_city":true}}

User: "now 2 adults and 1 child"
Return:
{{"set_adults":2,"set_children":1}}

User: "actually 2 rooms"
Return:
{{"set_rooms":2}}

User: "for 4 adults"
Return:
{{"set_adults":4}}

User: "dates do not matter anymore"
Return:
{{"clear_dates":true}}
""".strip()

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY/GOOGLE_API_KEY")

    llm = Gemini(
        model="models/gemini-2.0-flash",
        api_key=api_key,
    )

    return Agent(
        name="intent_update",
        model=llm,
        instruction=instruction,
    )