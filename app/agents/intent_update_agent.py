import json
import os

from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini

from app.schemas.intent_patch import SearchIntentPatch


def build_intent_update_agent() -> Agent:
    schema = SearchIntentPatch.model_json_schema()

    instruction = f"""
You update an existing search request.

Return ONLY JSON matching schema:
{json.dumps(schema, ensure_ascii=False)}

You receive:
- previous state
- new user message

Rules:

- Do NOT rebuild full intent
- Only return CHANGES

Examples:

"add kettle"
→ add_must_have_fields = ["kettle"]

"not in Baku, but Tbilisi"
→ set_city = "Tbilisi"

"kitchen is not required anymore"
→ remove_must_have_fields = ["kitchen"]

"at least 3 bedrooms"
→ set_filters.bedrooms_min = 3
"""

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    llm = Gemini(
        model="models/gemini-2.0-flash",
        api_key=api_key,
    )

    return Agent(
        name="intent_update",
        model=llm,
        instruction=instruction,
    )