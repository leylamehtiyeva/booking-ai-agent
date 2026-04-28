from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Literal

from pydantic import BaseModel, Field
from app.schemas.fallback_policy import FallbackPolicy

from app.logic.listing_signals import collect_listing_signals
from app.schemas.constraints import (
    ConstraintMappingStatus,
    ConstraintPriority,
    EvidenceStrategy,
    UserConstraint,
)
from app.schemas.fields import Field as CanonicalField
from app.schemas.listing import ListingRaw
from app.schemas.match import Ternary

ResolverType = Literal["textual", "geo", "hybrid"]
DecisionType = Literal["YES", "NO", "UNCERTAIN"]
ResolutionStatus = Literal["matched", "failed", "uncertain"]


class ConstraintEvidence(BaseModel):
    snippet: str
    source: str
    path: str | None = None


class ConstraintResolutionRequest(BaseModel):
    listing_id: str | None = None
    listing_title: str | None = None

    constraint_id: str | None = None
    raw_text: str
    normalized_text: str

    priority: str
    category: str
    mapping_status: str
    evidence_strategy: str
    mapped_fields: list[str] = Field(default_factory=list)

    structured_value: Literal["YES", "NO", "UNCERTAIN"] | None = None
    resolver_type: ResolverType = "textual"

    listing_evidence: list[dict[str, str]] = Field(default_factory=list)


class ConstraintResolutionResult(BaseModel):
    listing_id: str | None = None
    listing_title: str | None = None

    constraint_id: str | None = None
    raw_text: str
    normalized_text: str

    resolver_type: ResolverType
    decision: DecisionType
    resolution_status: ResolutionStatus
    confidence: float | None = None
    reason: str

    evidence: list[ConstraintEvidence] = Field(default_factory=list)

    source_stage: Literal["fallback"] = "fallback"
    structured_value_before: Literal["YES", "NO", "UNCERTAIN"] | None = None
    explicit_negative: bool = False


def _gemini_client():
    try:
        from google.genai import Client
    except ImportError as e:
        raise ImportError("google-genai is not installed") from e

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Missing GOOGLE_API_KEY")
    return Client(api_key=api_key)


def _genai_types():
    try:
        from google.genai import types as genai_types
    except ImportError as e:
        raise ImportError("google-genai is not installed") from e
    return genai_types


def _decision_to_status(decision: DecisionType) -> ResolutionStatus:
    return {
        "YES": "matched",
        "NO": "failed",
        "UNCERTAIN": "uncertain",
    }[decision]
    
def _normalize_evidence_strategy_for_resolution(strategy: str | None) -> str:
    if strategy == "geo":
        return "textual"
    return strategy or "textual"


def _extract_json(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    return text


def _source_from_path(path: str) -> str:
    if path.startswith("listing.facilities"):
        return "facilities"
    if path.startswith("rooms["):
        return "room_facilities"
    if path.startswith("policies["):
        return "policies"
    if path.startswith("highlights["):
        return "highlights"
    if path.startswith("listing.description"):
        return "description"
    if path.startswith("listing.name"):
        return "title"
    if path.startswith("listing.property_type"):
        return "property_type"
    return "other"


def _has_explicit_negative(evidence: list[ConstraintEvidence]) -> bool:
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
    joined = " ".join((e.snippet or "").lower() for e in evidence)
    return any(marker in joined for marker in negative_markers)


def _normalize_result(raw: dict[str, Any], req: ConstraintResolutionRequest) -> ConstraintResolutionResult:
    decision = str(raw.get("decision", "UNCERTAIN")).upper().strip()
    if decision not in {"YES", "NO", "UNCERTAIN"}:
        decision = "UNCERTAIN"

    evidence = [
        ConstraintEvidence(
            snippet=str(e.get("snippet", "")).strip(),
            source=str(e.get("source", "other")).strip() or "other",
            path=e.get("path"),
        )
        for e in raw.get("evidence", [])
        if isinstance(e, dict)
    ]

    explicit_negative = _has_explicit_negative(evidence)

    if decision == "NO" and not explicit_negative:
        decision = "UNCERTAIN"

    reason = str(raw.get("reason") or "").strip()
    if not reason:
        if decision == "YES":
            reason = f"{req.normalized_text} is explicitly supported by listing text."
        elif decision == "NO":
            reason = f"{req.normalized_text} is explicitly unavailable in the listing."
        else:
            reason = f"{req.normalized_text} is not explicitly confirmed in the listing."

    return ConstraintResolutionResult(
        listing_id=req.listing_id,
        listing_title=req.listing_title,
        constraint_id=req.constraint_id,
        raw_text=req.raw_text,
        normalized_text=req.normalized_text,
        resolver_type=req.resolver_type,
        decision=decision,
        resolution_status=_decision_to_status(decision),
        confidence=raw.get("confidence"),
        reason=reason,
        evidence=evidence,
        structured_value_before=req.structured_value,
        explicit_negative=explicit_negative,
    )


def _prepare_listing_evidence(
    listing: ListingRaw,
    max_items: int = 40,
    max_chars: int = 240,
) -> list[dict[str, str]]:
    source_rank = {
        "facilities": 0,
        "room_facilities": 1,
        "policies": 2,
        "highlights": 3,
        "description": 4,
        "title": 5,
        "property_type": 6,
        "other": 7,
    }

    prepared: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for signal in collect_listing_signals(listing):
        path = (signal.path or "").strip()
        raw_text = (signal.raw_text or signal.text or "").strip()
        if not path or not raw_text:
            continue

        snippet = raw_text[:max_chars]
        key = (path, snippet.casefold())
        if key in seen:
            continue
        seen.add(key)

        prepared.append(
            {
                "source": _source_from_path(path),
                "path": path,
                "text": snippet,
            }
        )

    prepared.sort(key=lambda x: (source_rank.get(x["source"], 999), len(x["text"])))
    return prepared[:max_items]


def _build_system_prompt() -> str:
    return """
You resolve whether a booking listing satisfies one user constraint using only the provided listing evidence.

Return only valid JSON:
{
  "decision": "YES" | "NO" | "UNCERTAIN",
  "confidence": 0.0,
  "reason": "short factual explanation",
  "evidence": [
    {
      "snippet": "string",
      "source": "facilities|room_facilities|policies|highlights|description|title|property_type|other",
      "path": "string|null"
    }
  ]
}

Core decision rules:
- Return YES only when the evidence clearly confirms the constraint.
- Return NO when the evidence clearly contradicts the constraint.
- Return UNCERTAIN when the evidence is missing, vague, weak, conditional, or insufficient.

Important distinction:
- Missing evidence -> UNCERTAIN.
- Weak or partial evidence -> UNCERTAIN.
- Conditional evidence -> UNCERTAIN unless the condition clearly makes the constraint unavailable for the user.
- Explicit contradiction -> NO.

What counts as contradiction:
- The user asks for something to be free/included, but evidence says it is paid, costs extra, has a fee, or is not included.
- The user asks for something to be allowed, but evidence says it is not allowed, prohibited, restricted, or forbidden.
- The user asks for something to be available, but evidence says it is unavailable, absent, closed, not provided, or not available to guests.
- The user asks for something private, but evidence says it is shared.
- The user asks for something on-site/in the property, but evidence says it is only nearby, off-site, or public.
- The user forbids something, but evidence says that thing is allowed or present.
- A policy contradicts a facility/description claim; in conflicts, policies usually override marketing descriptions.

Do not return UNCERTAIN when the evidence explicitly contradicts the constraint.

Conservatism rule:
- Be conservative to avoid false YES.
- Do not use conservatism to avoid NO when contradiction is explicit.

Evidence rules:
- Use only provided evidence.
- Do not invent evidence.
- Cite the exact snippet that supports the decision.
- Prefer direct evidence from policies, facilities, room_facilities, or highlights.
- Description/title can support a decision, but are weaker than policy/facility evidence.
""".strip()


def is_constraint_fallback_eligible(
    constraint: UserConstraint,
    *,
    structured_value: Ternary | None,
    policy: FallbackPolicy,
) -> bool:
    if not policy.enabled:
        return False

    if policy.must_only and constraint.priority != ConstraintPriority.MUST:
        return False

    if (
        policy.run_for_unresolved
        and constraint.mapping_status == ConstraintMappingStatus.UNRESOLVED
    ):
        return True

    if (
        policy.run_for_structured_uncertain
        and structured_value == Ternary.UNCERTAIN
    ):
        return True

    return False

def build_resolution_request(
    *,
    listing: ListingRaw,
    constraint: UserConstraint,
    structured_value: Ternary | None,
) -> ConstraintResolutionRequest:
    normalized_strategy = _normalize_evidence_strategy_for_resolution(
        constraint.evidence_strategy.value
    )

    return ConstraintResolutionRequest(
        listing_id=getattr(listing, "id", None),
        listing_title=getattr(listing, "name", None),
        constraint_id=getattr(constraint, "id", None),
        raw_text=constraint.raw_text,
        normalized_text=constraint.normalized_text,
        priority=constraint.priority.value,
        category=constraint.category.value,
        mapping_status=constraint.mapping_status.value,
        evidence_strategy=normalized_strategy,
        mapped_fields=[f.value if hasattr(f, "value") else str(f) for f in (constraint.mapped_fields or [])],
        structured_value=structured_value.value if structured_value is not None else None,
        resolver_type="textual",
        listing_evidence=_prepare_listing_evidence(listing),
    )
from app.config.llm import get_gemini_model


async def resolve_constraint_via_textual_evidence(
    req: ConstraintResolutionRequest,
    *,
    model: str = get_gemini_model(),
) -> ConstraintResolutionResult:
    payload = {
        "constraint": {
            "raw_text": req.raw_text,
            "normalized_text": req.normalized_text,
            "priority": req.priority,
            "category": req.category,
            "mapping_status": req.mapping_status,
            "evidence_strategy": req.evidence_strategy,
            "mapped_fields": req.mapped_fields,
            "structured_value": req.structured_value,
        },
        "listing_evidence": req.listing_evidence,
    }

    system = _build_system_prompt()
    user_prompt = json.dumps(payload, ensure_ascii=False)
    print("SYSTEM PROMPT USED:")
    print(system)

    def _call_sync() -> ConstraintResolutionResult:
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

        raw_text = resp.text or ""
        raw_json = _extract_json(raw_text)

        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            return _normalize_result(
                {
                    "status": "UNCERTAIN",
                    "answer": "UNCERTAIN",
                    "snippet": None,
                    "source": "llm_fallback",
                    "reason": (
                        "LLM fallback returned invalid JSON. "
                        f"Raw response: {raw_text[:300]}"
                    ),
                },
                req,
            )

        return _normalize_result(data, req)

    return await asyncio.to_thread(_call_sync)


async def resolve_listing_constraints_with_fallback(
    *,
    listing: ListingRaw,
    constraints: list[UserConstraint],
    structured_matches_by_field: dict[CanonicalField, Any],
    policy: FallbackPolicy,
) -> list[ConstraintResolutionResult]:
    if not policy.enabled:
        return []

    results: list[ConstraintResolutionResult] = []
    max_constraints = policy.normalized_max_constraints_per_listing()

    for constraint in constraints or []:
        if len(results) >= max_constraints:
            break

        structured_value: Ternary | None = None

        if constraint.mapping_status == ConstraintMappingStatus.KNOWN and constraint.mapped_fields:
            field = constraint.mapped_fields[0]
            fm = structured_matches_by_field.get(field)
            structured_value = fm.value if fm is not None else None

        if not is_constraint_fallback_eligible(
            constraint,
            structured_value=structured_value,
            policy=policy,
        ):
            continue

        req = build_resolution_request(
            listing=listing,
            constraint=constraint,
            structured_value=structured_value,
        )
        result = await resolve_constraint_via_textual_evidence(
            req,
            model=policy.model,
        )
        results.append(result)

    return results