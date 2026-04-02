from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from pydantic import BaseModel, Field


def _cleanup_model_text(text: str) -> str:
    text = (text or "").strip()
    text = text.replace(
        "Both GOOGLE_API_KEY and GEMINI_API_KEY are set. Using GOOGLE_API_KEY.",
        "",
    ).strip()
    return text

STRUCTURED_SOURCE_PREFIXES = (
    "listing.facilities",
    "rooms[",
    "policies[",
    "highlights[",
)

WEAKER_SOURCE_PREFIXES = (
    "listing.description",
    "fine_print",
)


class UnknownFieldEvidence(BaseModel):
    source_path: str
    snippet: str


class UnknownFieldSearchResult(BaseModel):
    query_text: str
    value: str  # FOUND | NOT_FOUND | UNCERTAIN
    reason: str
    evidence: list[UnknownFieldEvidence] = Field(default_factory=list)


def _gemini_client():
    try:
        from google.genai import Client
    except ImportError as e:
        raise ImportError("google-genai is not installed") from e

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY/GOOGLE_API_KEY")
    return Client(api_key=api_key)


def _genai_types():
    try:
        from google.genai import types as genai_types
    except ImportError as e:
        raise ImportError("google-genai is not installed") from e
    return genai_types


def _source_rank(path: str) -> int:
    for prefix in STRUCTURED_SOURCE_PREFIXES:
        if path.startswith(prefix):
            return 0
    for prefix in WEAKER_SOURCE_PREFIXES:
        if path.startswith(prefix):
            return 1
    return 2


def _prepare_listing_evidence(signals: list[Any], max_items: int = 80) -> list[dict[str, str]]:
    """
    Keep the most useful evidence lines, prioritizing structured sources over description.
    Supports ListingSignal objects or plain dicts.
    """
    cleaned: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for item in signals or []:
        if isinstance(item, dict):
            path = (item.get("path") or "").strip()
            text = (item.get("text") or "").strip()
        else:
            path = (getattr(item, "path", None) or "").strip()
            text = (getattr(item, "text", None) or "").strip()

        if not path or not text:
            continue

        key = (path, text)
        if key in seen:
            continue
        seen.add(key)

        cleaned.append({"path": path, "text": text})

    cleaned.sort(key=lambda x: (_source_rank(x["path"]), len(x["text"])))
    return cleaned[:max_items]


def _build_system_prompt() -> str:
    return """
You are checking whether a listing contains evidence for a user-requested must-have attribute that is not part of the structured schema.

You will receive:
- a user attribute query, such as "satellite TV" or "ironing facilities"
- listing evidence snippets, each with a source path

Your job:
- decide whether the listing clearly contains that attribute
- prefer direct evidence from facilities, room facilities, policies, or highlights
- use description only as weaker evidence
- be conservative

Return only valid JSON with this schema:
{
  "value": "FOUND" | "NOT_FOUND" | "UNCERTAIN",
  "reason": "short explanation",
  "evidence": [
    {
      "source_path": "string",
      "snippet": "string"
    }
  ]
}

Rules:
- Use FOUND only when the attribute is directly supported by the evidence.
- Use NOT_FOUND only when the evidence explicitly says the attribute is unavailable, disallowed, absent, or not provided.
- If the attribute is not explicitly mentioned, return UNCERTAIN.
- If the attribute is only weakly implied, return UNCERTAIN.
- Do NOT infer too much from loosely related wording.
- Do NOT invent evidence.
- Keep reason short and factual.
- Do NOT say "in the provided snippets".
- Prefer user-facing reasons like:
  - "<attribute> is explicitly mentioned in the listing."
  - "<attribute> is explicitly unavailable in the listing."
  - "<attribute> is not explicitly mentioned in the listing."
- Treat close equivalents as valid evidence when they clearly mean the same thing.
  Example: "satellite channels" is strong evidence for "satellite TV".
- Do NOT treat broad or related amenities as equivalent if the match is weak.
  Example: "flat-screen TV" alone is NOT enough evidence for "satellite TV".

Examples:
- Query: "satellite TV"
  Evidence: "Satellite channels"
  -> FOUND

- Query: "satellite TV"
  Evidence: no mention of satellite TV or satellite channels
  -> UNCERTAIN

- Query: "satellite TV"
  Evidence: "No satellite channels"
  -> NOT_FOUND
""".strip()

def _extract_json(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    return text


async def search_unknown_must_have_evidence(
    *,
    query_text: str,
    listing_signals: list[dict[str, str]],
    model: str = "gemini-2.0-flash",
) -> UnknownFieldSearchResult:
    prepared_signals = _prepare_listing_evidence(listing_signals)

    user_payload = {
        "query_text": query_text,
        "listing_evidence": prepared_signals,
    }

    system = _build_system_prompt()
    user_prompt = json.dumps(user_payload, ensure_ascii=False, indent=2)

    def _call_sync() -> UnknownFieldSearchResult:
        client = _gemini_client()
        genai_types = _genai_types()

        resp = client.models.generate_content(
            model=model,
            contents=[
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=user_prompt)],
                )
            ],
            config=genai_types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.1,
            ),
        )

        raw_text = _cleanup_model_text(resp.text or "")
        raw = _extract_json(raw_text)
        data = json.loads(raw)

        result = UnknownFieldSearchResult(
            query_text=query_text,
            value=data["value"],
            reason=data["reason"],
            evidence=[
                UnknownFieldEvidence(
                    source_path=e["source_path"],
                    snippet=e["snippet"],
                )
                for e in data.get("evidence", [])
            ],
        )

        return _normalize_unknown_field_result(result)

    return await asyncio.to_thread(_call_sync)


def _normalize_unknown_field_result(result: UnknownFieldSearchResult) -> UnknownFieldSearchResult:
    """
    Safety rule:
    - NOT_FOUND is allowed only when there is explicit negative evidence.
    - If there is no evidence at all, downgrade NOT_FOUND -> UNCERTAIN.
    """
    if result.value != "NOT_FOUND":
        return result

    if not result.evidence:
        return UnknownFieldSearchResult(
            query_text=result.query_text,
            value="UNCERTAIN",
            reason=f"{result.query_text} is not explicitly mentioned in the listing.",
            evidence=[],
        )

    negative_markers = (
        "no ",
        "not allowed",
        "not available",
        "unavailable",
        "without ",
        "does not have",
        "is not provided",
        "not provided",
        "absent",
    )

    evidence_text = " ".join(e.snippet.lower() for e in result.evidence)
    has_explicit_negative = any(marker in evidence_text for marker in negative_markers)

    if not has_explicit_negative:
        return UnknownFieldSearchResult(
            query_text=result.query_text,
            value="UNCERTAIN",
            reason=f"{result.query_text} is not explicitly mentioned in the listing.",
            evidence=result.evidence,
        )

    return result