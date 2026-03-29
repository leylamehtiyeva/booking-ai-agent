from __future__ import annotations

import asyncio
import json
from typing import List

from google import genai
from google.genai import types as genai_types

from app.logic.listing_signals import collect_listing_signals
from app.schemas.fields import Field
from app.schemas.listing import ListingRaw
from app.schemas.match import Evidence, EvidenceSource, FieldMatch, Ternary


LLM_FALLBACK_FIELDS = {
    Field.KITCHEN,
    Field.PRIVATE_BATHROOM,
    Field.WIFI,
    Field.AIR_CONDITIONING,
    Field.WASHING_MACHINE,
    Field.OVEN,
    Field.MICROWAVE,
    Field.REFRIGERATOR,
    Field.BALCONY,
    Field.KETTLE,
    Field.COFFEE_MACHINE,
    Field.FREE_CANCELLATION,
    Field.PET_FRIENDLY,
    Field.PROPERTY_APARTMENT,
}


FIELD_DESCRIPTIONS = {
    Field.KITCHEN: "Whether the accommodation has a kitchen or kitchenette.",
    Field.PRIVATE_BATHROOM: "Whether the accommodation has a private bathroom, not shared.",
    Field.WIFI: "Whether Wi-Fi / internet access is available.",
    Field.AIR_CONDITIONING: "Whether air conditioning is available.",
    Field.WASHING_MACHINE: "Whether a washing machine is available.",
    Field.OVEN: "Whether an oven is available.",
    Field.MICROWAVE: "Whether a microwave is available.",
    Field.REFRIGERATOR: "Whether a refrigerator / fridge is available.",
    Field.BALCONY: "Whether the accommodation has a balcony, terrace, or patio.",
    Field.KETTLE: "Whether a kettle / electric kettle is available.",
    Field.COFFEE_MACHINE: "Whether a coffee machine / coffee maker is available.",
    Field.FREE_CANCELLATION: "Whether the booking includes free cancellation.",
    Field.PET_FRIENDLY: "Whether pets are allowed.",
    Field.PROPERTY_APARTMENT: "Whether this accommodation is an apartment.",
}


def _gemini_client() -> genai.Client:
    return genai.Client()


def _build_fallback_context(listing: ListingRaw, max_signals: int = 25) -> str:
    """
    Build short text context from normalized signals.
    We don't send the whole raw JSON to the model.
    """
    signals = collect_listing_signals(listing)

    useful_prefixes = (
        "listing.name",
        "listing.property_type",
        "listing.description",
        "listing.facilities",
        "rooms[",
        "highlights",
        "policies",
    )

    filtered = [
        s for s in signals
        if any(s.path.startswith(prefix) for prefix in useful_prefixes)
    ]

    parts: List[str] = []
    for s in filtered[:max_signals]:
        parts.append(f"{s.path}: {s.raw_text}")

    return "\n".join(parts)


def _extract_json_object(text: str) -> dict:
    text = (text or "").strip()

    # direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # try fenced json
    if "```" in text:
        stripped = text.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(stripped)
        except Exception:
            pass

    # fallback: extract outermost {...}
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        return json.loads(candidate)

    raise ValueError("Could not parse JSON from model response")


async def classify_field_from_description(
    listing: ListingRaw,
    field: Field,
    model: str = "gemini-2.0-flash",
) -> FieldMatch:
    """
    LLM fallback for a single unresolved field.

    Use ONLY when deterministic matcher returned UNCERTAIN.
    Returns YES / NO / UNCERTAIN with reason as evidence.
    """
    if field not in LLM_FALLBACK_FIELDS:
        return FieldMatch(value=Ternary.UNCERTAIN, confidence=0.0, evidence=[])

    field_description = FIELD_DESCRIPTIONS.get(field, field.value)
    context = _build_fallback_context(listing)

    if not context.strip():
        return FieldMatch(value=Ternary.UNCERTAIN, confidence=0.0, evidence=[])

    system = (
        "You are a careful property listing classifier.\n"
        "Your task is to classify ONE requested property feature using ONLY the provided listing evidence.\n"
        "Return ONLY valid JSON. No markdown. No explanation outside JSON.\n"
        'Allowed result values: "YES", "NO", "UNCERTAIN".\n'
        "Use YES only if the evidence clearly supports the feature.\n"
        "Use NO only if the evidence clearly contradicts the feature.\n"
        "Use UNCERTAIN if the evidence is missing, vague, or ambiguous.\n"
        "Do not guess.\n"
        'Return JSON with exactly these keys: {"result": "...", "reason": "..."}\n'
        "The reason must be short and based on the evidence.\n"
    )

    payload = {
        "field": field.value,
        "field_description": field_description,
        "listing_name": getattr(listing, "name", None),
        "evidence": context,
        "output_schema": {
            "result": 'one of ["YES", "NO", "UNCERTAIN"]',
            "reason": "short evidence-based explanation",
        },
    }

    def _call_sync() -> dict:
        client = _gemini_client()
        resp = client.models.generate_content(
            model=model,
            contents=[
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=json.dumps(payload, ensure_ascii=False))],
                )
            ],
            config=genai_types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.0,
            ),
        )
        return _extract_json_object(resp.text or "")

    try:
        data = await asyncio.to_thread(_call_sync)
    except Exception:
        return FieldMatch(value=Ternary.UNCERTAIN, confidence=0.0, evidence=[])

    raw_result = str(data.get("result", "")).strip().upper()
    reason = str(data.get("reason", "")).strip()

    ternary_map = {
        "YES": Ternary.YES,
        "NO": Ternary.NO,
        "UNCERTAIN": Ternary.UNCERTAIN,
    }
    value = ternary_map.get(raw_result, Ternary.UNCERTAIN)

    confidence = {
        Ternary.YES: 0.7,
        Ternary.NO: 0.7,
        Ternary.UNCERTAIN: 0.4,
    }[value]

    evidence = []
    if reason:
        evidence = [
            Evidence(
                source=EvidenceSource.LLM,
                path="llm_fallback.description",
                snippet=reason,
            )
        ]

    return FieldMatch(
        value=value,
        confidence=confidence,
        evidence=evidence,
    )