from __future__ import annotations
from app.schemas.property_semantics import OccupancyType, PropertyType
import asyncio
import json
import os
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from google.genai import Client
from google.genai import types as genai_types
from pydantic import ValidationError
from app.agents.intent_router_agent import IntentRoute
from app.config import MAX_ITEMS_DEFAULT, MAX_ITEMS_HARD_CAP
from app.logic.llm_field_fallback import classify_field_from_description
from app.logic.matcher_structured import match_listing_structured
from app.logic.numeric_filters import evaluate_numeric_filters
from app.retrieval import Source, get_candidates
from app.schemas.fields import Field
from app.schemas.listing import ListingRaw
from app.schemas.match import Ternary
from app.schemas.query import SearchRequest
from app.logic.property_semantics import match_occupancy_types, match_property_types
from app.schemas.match import Ternary
from app.logic.normalize_search_response import normalize_search_response
from app.logic.listing_signals import collect_listing_signals
from app.logic.unknown_field_evidence_search import search_unknown_must_have_evidence
from app.logic.request_resolution import resolve_required_search_context
from app.logic.unresolved_constraint_utils import get_unresolved_must_constraints
from app.logic.occupancy import evaluate_occupancy
from app.logic.constraint_state import (
    build_constraints_from_legacy_state,
    sync_legacy_state_from_constraints,
)


def _has_explicit_negative_unknown_evidence(item: dict) -> bool:
    evidence = item.get("evidence") or []
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

    for ev in evidence:
        if isinstance(ev, dict):
            snippet = (ev.get("snippet") or "").lower()
        else:
            snippet = (getattr(ev, "snippet", None) or "").lower()

        if any(marker in snippet for marker in negative_markers):
            return True

    return False


def _score_unknown_request_results(
    unknown_results: list[dict] | None,
) -> tuple[float, list[str]]:
    """
    Soft score adjustment for unresolved must-have constraint evidence search.

    Rules:
    - FOUND: +3
    - UNCERTAIN: +0
    - NOT_FOUND with explicit negative evidence: -4
    - NOT_FOUND without explicit negative evidence: +0
    """
    delta = 0.0
    reasons: list[str] = []

    for item in unknown_results or []:
        constraint = item.get("constraint") or {}
        label = (
            constraint.get("normalized_text")
            or item.get("query_text")
            or "Unresolved constraint"
        )
        value = item.get("value")

        if value == "FOUND":
            delta += 3.0
            reasons.append(f"CONSTRAINT_MATCH: {label} confirmed")
        elif value == "NOT_FOUND":
            if _has_explicit_negative_unknown_evidence(item):
                delta -= 4.0
                reasons.append(f"CONSTRAINT_MATCH: {label} explicitly not supported")
        elif value == "UNCERTAIN":
            reasons.append(f"CONSTRAINT_MATCH: {label} not confirmed")

    return delta, reasons

def _fails_must(matches: dict[Field, Any], must_fields: List[Field] | None) -> bool:
    """Strict must-have filter: if any must field is explicitly NO -> reject."""
    for f in (must_fields or []):
        fm = matches.get(f)
        if fm is not None and fm.value == Ternary.NO:
            return True
    return False

def _fails_numeric_filters(numeric_results: List[Any] | None) -> bool:
    """
    Strict numeric filter: if any numeric constraint is explicitly NO -> reject.
    UNCERTAIN is allowed.
    """
    for r in (numeric_results or []):
        if r.value == Ternary.NO:
            return True
    return False


async def _attach_unknown_request_results(
    req: SearchRequest,
    ranked_items: list[dict],
) -> list[dict]:
    """
    For unresolved must-have constraints, run evidence search per listing and
    attach results to each ranked item.

    This step does NOT yet hard-filter results. It only enriches them.
    """
    unresolved_constraints = get_unresolved_must_constraints(req)
    if not unresolved_constraints:
        return ranked_items

    for item in ranked_items:
        listing = item.get("listing")
        if listing is None:
            item["unknown_request_results"] = []
            continue

        signals = collect_listing_signals(listing)
        unknown_results = []

        for constraint in unresolved_constraints:
            try:
                result = await search_unknown_must_have_evidence(
                    query_text=constraint.normalized_text,
                    listing_signals=signals,
                )
                payload = result.model_dump(mode="json")
                payload["constraint"] = {
                    "raw_text": constraint.raw_text,
                    "normalized_text": constraint.normalized_text,
                    "priority": constraint.priority.value,
                    "category": constraint.category.value,
                    "mapping_status": constraint.mapping_status.value,
                    "evidence_strategy": constraint.evidence_strategy.value,
                }
                unknown_results.append(payload)
            except Exception as e:
                unknown_results.append(
                    {
                        "query_text": constraint.normalized_text,
                        "value": "UNCERTAIN",
                        "reason": f"{constraint.normalized_text} could not be verified from the listing.",
                        "evidence": [],
                        "error": str(e),
                        "constraint": {
                            "raw_text": constraint.raw_text,
                            "normalized_text": constraint.normalized_text,
                            "priority": constraint.priority.value,
                            "category": constraint.category.value,
                            "mapping_status": constraint.mapping_status.value,
                            "evidence_strategy": constraint.evidence_strategy.value,
                        },
                    }
                )

        item["unknown_request_results"] = unknown_results

    return ranked_items

def _parse_iso_date(x: Any) -> Optional[date]:
    if x is None:
        return None
    if isinstance(x, date):
        return x
    if isinstance(x, str):
        try:
            return date.fromisoformat(x.strip())
        except ValueError:
            return None
    return None


def _covers_dates(lst: ListingRaw, check_in: date, check_out: date) -> bool:
    """MVP availability filter for fixtures (safety net).

    Apify typically returns listings already scoped to (city, dates),
    but mocks may contain mixed availability.
    """
    ad = getattr(lst, "available_dates", None)
    if ad is None:
        return True

    if isinstance(ad, dict):
        lst_in_raw = ad.get("check_in")
        lst_out_raw = ad.get("check_out")
    else:
        lst_in_raw = getattr(ad, "check_in", None)
        lst_out_raw = getattr(ad, "check_out", None)

    lst_in = _parse_iso_date(lst_in_raw)
    lst_out = _parse_iso_date(lst_out_raw)

    if lst_in is None or lst_out is None:
        return True

    return lst_in <= check_in and check_out <= lst_out


def _gemini_client() -> Client:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY/GOOGLE_API_KEY")
    return Client(api_key=api_key)


async def _repair_intent_with_llm(
    intent_raw: Dict[str, Any],
    errors: list[dict],
    model: str = "gemini-2.0-flash",
) -> Dict[str, Any]:
    """Ask LLM to repair intent so it matches IntentRoute exactly.

    Contract:
    - constraints is the canonical semantic state
    - unknown_requests is NOT the semantic fallback target
    - invalid legacy enum-like items may be dropped from enum slots; they can be
      reported separately as dropped_requests later by the salvage layer
    """
    allowed_values = [f.value for f in Field]

    system = (
        "You are a JSON repair assistant.\n"
        "Return ONLY a valid JSON object. No markdown. No code fences.\n"
        "Fix the JSON to match the target schema EXACTLY.\n"
        "constraints is the source of truth for user constraints.\n"
        "Do NOT invent new keys.\n"
        "Do NOT use unknown_requests as a semantic fallback bucket.\n"
        "If a legacy enum-like item cannot be mapped safely, remove it from that enum list.\n"
        "Preserve meaningful user meaning inside constraints whenever possible.\n"
    )

    payload = {
        "allowed_fields": allowed_values,
        "validation_errors": errors,
        "input_intent": intent_raw,
        "target_schema": {
            "city": "string|null",
            "check_in": "YYYY-MM-DD|null",
            "check_out": "YYYY-MM-DD|null",
            "nights": "int|null",
            "adults": "int|null",
            "children": "int|null",
            "rooms": "int|null",
            "constraints": [
                {
                    "raw_text": "string",
                    "normalized_text": "string",
                    "priority": "must|nice|forbidden",
                    "category": "amenity|policy|location|layout|numeric|property_type|occupancy|other",
                    "mapping_status": "known|unresolved",
                    "mapped_fields": "list[canonical_key]",
                    "evidence_strategy": "structured|textual|geo|none",
                }
            ],
            "filters": {
                "bedrooms_min": "int|null",
                "bedrooms_max": "int|null",
                "area_sqm_min": "float|null",
                "area_sqm_max": "float|null",
                "bathrooms_min": "float|null",
                "bathrooms_max": "float|null",
                "price": {
                    "min_amount": "float|null",
                    "max_amount": "float|null",
                    "currency": "string|null",
                    "scope": "per_night|total_stay|null",
                },
            },
            "property_types": [
                "apartment|hotel|hostel|house|aparthotel|guesthouse"
            ],
            "occupancy_types": [
                "entire_place|private_room|shared_room|hotel_room"
            ],
        },
    }

    def _call_sync() -> Dict[str, Any]:
        client = _gemini_client()
        resp = client.models.generate_content(
            model=model,
            contents=[
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=json.dumps(payload, ensure_ascii=False))],
                )
            ],
            config=genai_types.GenerateContentConfig(system_instruction=system),
        )
        text = (resp.text or "").strip()
        return json.loads(text)

    return await asyncio.to_thread(_call_sync)


def _salvage_only_enum_keys(intent_dict: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Keep only safely parseable enum-based values and collect dropped legacy residue separately.

    Contract:
    - returned intent dict is safe to validate as IntentRoute
    - unknown_requests is not used as a salvage bucket
    - dropped_requests contains invalid legacy enum-like items that could not be preserved
    """
    dropped_requests: list[str] = []

    out: Dict[str, Any] = {
        "city": intent_dict.get("city"),
        "check_in": intent_dict.get("check_in"),
        "check_out": intent_dict.get("check_out"),
        "nights": intent_dict.get("nights"),
        "adults": intent_dict.get("adults"),
        "children": intent_dict.get("children"),
        "rooms": intent_dict.get("rooms"),
        "constraints": intent_dict.get("constraints") or [],
        "must_have_fields": [],
        "nice_to_have_fields": [],
        "filters": intent_dict.get("filters") or {},
        "property_types": [],
        "occupancy_types": [],
        "unknown_requests": [],
    }

    def parse_enum_list(xs, enum_cls):
        ok = []
        for x in xs or []:
            if isinstance(x, enum_cls):
                ok.append(x)
                continue

            if isinstance(x, str):
                s = x.strip()

                try:
                    ok.append(enum_cls(s))
                    continue
                except Exception:
                    pass

                try:
                    ok.append(enum_cls[s])
                    continue
                except Exception:
                    pass

                try:
                    ok.append(enum_cls[s.upper()])
                    continue
                except Exception:
                    pass

                if s:
                    dropped_requests.append(s)
            else:
                dropped_requests.append(str(x))
        return ok

    out["must_have_fields"] = parse_enum_list(intent_dict.get("must_have_fields"), Field)
    out["nice_to_have_fields"] = parse_enum_list(intent_dict.get("nice_to_have_fields"), Field)
    out["property_types"] = parse_enum_list(intent_dict.get("property_types"), PropertyType)
    out["occupancy_types"] = parse_enum_list(intent_dict.get("occupancy_types"), OccupancyType)

    seen: set[str] = set()
    deduped_dropped: list[str] = []
    for item in dropped_requests:
        cleaned = item.strip()
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        deduped_dropped.append(cleaned)

    return out, deduped_dropped

async def _validate_and_repair_intent(intent: Any, attempts: int = 2) -> Tuple[IntentRoute, List[str]]:
    """Validate intent as IntentRoute with up to N LLM repair attempts.

    Returns (intent_obj, dropped_requests).

    dropped_requests:
    - invalid legacy enum-like residue we could not preserve cleanly
    - NOT compatibility unknown_requests
    - NOT canonical unresolved constraints
    """
    intent_work: Dict[str, Any] = intent if isinstance(intent, dict) else {}
    dropped_requests: list[str] = []

    intent_obj: Optional[IntentRoute] = None
    for _ in range(max(0, attempts)):
        try:
            intent_obj = IntentRoute.model_validate(intent_work)
            break
        except ValidationError as e:
            try:
                intent_work = await _repair_intent_with_llm(intent_work, e.errors())
            except Exception:
                break

    if intent_obj is None:
        try:
            intent_obj = IntentRoute.model_validate(intent_work)
        except ValidationError:
            salvaged, salvage_dropped = _salvage_only_enum_keys(intent_work)
            dropped_requests.extend(salvage_dropped)
            intent_obj = IntentRoute.model_validate(salvaged)

    return intent_obj, dropped_requests


def _require_dates(intent_obj: IntentRoute) -> Tuple[Optional[date], Optional[date]]:
    return _parse_iso_date(getattr(intent_obj, "check_in", None)), _parse_iso_date(
        getattr(intent_obj, "check_out", None)
    )


def _build_request(
    user_text: str,
    intent_obj: IntentRoute,
    city: str,
    check_in: date,
    check_out: date,
) -> SearchRequest:
    req = SearchRequest(
        city=city,
        check_in=check_in,
        check_out=check_out,
        adults=intent_obj.adults or 2,
        children=intent_obj.children or 0,
        rooms=intent_obj.rooms or 1,
        currency="USD",
        budget_max=None,
        must_have_fields=[],
        nice_to_have_fields=[],
        forbidden_fields=[],
        min_guest_rating=None,
        filters=intent_obj.filters,
        property_types=intent_obj.property_types or None,
        occupancy_types=intent_obj.occupancy_types or None,
        constraints=intent_obj.constraints,
        unknown_requests=[],
    )

    # Canonical flow:
    # SearchRequest semantic state is carried by constraints.
    # Legacy fields are derived here only for compatibility/debug layers.
    return sync_legacy_state_from_constraints(req)


def _rank_structured(req: SearchRequest, listings: List[ListingRaw]) -> List[Dict[str, Any]]:
    ranked: List[Dict[str, Any]] = []
    for lst in listings:
        report = match_listing_structured(lst, req)
        numeric_results = evaluate_numeric_filters(
            lst,
            req.filters,
            check_in=req.check_in,
            check_out=req.check_out,
        )
        property_result = match_property_types(lst, req.property_types)
        occupancy_result = match_occupancy_types(lst, req.occupancy_types)
        # strict amenity must-have filter
        if _fails_must(report.matches, req.must_have_fields):
            continue

        # strict numeric filter
        if _fails_numeric_filters(numeric_results):
            continue
        
        if property_result is not None and property_result.value == Ternary.NO:
            continue

        if occupancy_result is not None and occupancy_result.value == Ternary.NO:
            continue

        score, must_yes, must_total, why = _score_listing(
            req,
            report.matches,
            numeric_results=numeric_results,
        )
        
        if property_result is not None:
            why.append(property_result.why)

        if occupancy_result is not None:
            why.append(occupancy_result.why)

        ranked.append(
            {
                "listing_name": lst.name,
                "listing_id": getattr(lst, "id", None),
                "report": report,
                "matches": report.matches,
                "numeric_results": numeric_results,
                "property_result": property_result,
                "occupancy_result": occupancy_result,
                "score": score,
                "must_have_matched": must_yes,
                "must_have_total": must_total,
                "why": why,
                "listing": lst,
            }
        )
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked

async def _apply_fallback_topk(req: SearchRequest, ranked: List[Dict[str, Any]], fallback_top_k: int) -> None:
    for item in ranked[: max(0, fallback_top_k)]:
        has_uncertain = any(
            item["matches"].get(f) is not None and item["matches"][f].value == Ternary.UNCERTAIN
            for f in (req.must_have_fields or [])
        )
        if not has_uncertain:
            continue

        for f in (req.must_have_fields or []):
            fm = item["matches"].get(f)
            if fm is not None and fm.value == Ternary.UNCERTAIN:
                fm2 = await classify_field_from_description(item["listing"], f)
                if fm2.value != Ternary.UNCERTAIN or fm2.evidence:
                    item["matches"][f] = fm2  # updates both item["matches"] and report.matches (same dict)

        # ✅ re-score after fallback
        score, must_yes, must_total, why = _score_listing(
            req,
            item["matches"],
            numeric_results=item.get("numeric_results"),
        )

        property_result = item.get("property_result")
        occupancy_result = item.get("occupancy_result")

        if property_result is not None and getattr(property_result, "why", None):
            why.append(property_result.why)

        if occupancy_result is not None and getattr(occupancy_result, "why", None):
            why.append(occupancy_result.why)

        item["score"] = score
        item["must_have_matched"] = must_yes
        item["must_have_total"] = must_total
        item["why"] = why

    ranked.sort(key=lambda x: x["score"], reverse=True)


def _format_results(req: SearchRequest, ranked: List[Dict[str, Any]], top_n: int, dropped_requests: List[str]) -> Dict[str, Any]:
    results_out = []
    for r in ranked[: max(0, top_n)]:
        lst = r.get("listing")
        results_out.append(
            {
                "title": r["listing_name"],
                "url": getattr(lst, "url", None),
                "id": getattr(lst, "id", None),
                "score": r["score"],
                "must": f"{r['must_have_matched']}/{r['must_have_total']}",
                "why": r["why"],
            }
        )


    not_found_fields = set()
    for r in ranked[: max(0, top_n)]:
        for f in (req.must_have_fields or []):
            fm = r["matches"].get(f)
            if fm is not None and fm.value == Ternary.NO:
                not_found_fields.add(f.value)

    notes = []
    if dropped_requests:
        notes.append(f"Could not map (ignored): {sorted(set(dropped_requests))}")
    if not_found_fields:
        notes.append(f"Not found in top results: {sorted(not_found_fields)}")

    summary = (
        f"city={req.city}, check_in={req.check_in}, check_out={req.check_out}, "
        f"must_have={[f.value for f in (req.must_have_fields or [])]}, "
        f"nice_to_have={[f.value for f in (req.nice_to_have_fields or [])]}, "
        f"property_types={[p.value for p in (req.property_types or [])]}, "
        f"occupancy_types={[o.value for o in (req.occupancy_types or [])]}"
    )
    if notes:
        summary += " | " + " | ".join(notes)

    return {
        "need_clarification": False,
        "summary": summary,
        "results": results_out,
    }


def _apply_unknown_request_scoring(ranked_items: list[dict]) -> list[dict]:
    """
    Apply soft score adjustments based on unknown must-have evidence search.
    """
    for item in ranked_items:
        unknown_results = item.get("unknown_request_results", [])
        delta, extra_why = _score_unknown_request_results(unknown_results)

        if delta != 0:
            item["score"] = float(item.get("score", 0.0)) + delta

        why = list(item.get("why") or [])
        why.extend(extra_why)
        item["why"] = why

    ranked_items.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return ranked_items


def _build_constraint_statuses(ranked_items: list[dict]) -> list[dict]:
    """
    Flatten unresolved-constraint fallback results into a response-friendly
    constraint status representation.
    """
    statuses: list[dict] = []

    for item in ranked_items:
        listing = item.get("listing")
        listing_id = getattr(listing, "id", None)
        listing_title = item.get("listing_name")

        for result in item.get("unknown_request_results", []) or []:
            constraint = result.get("constraint") or {}
            statuses.append(
                {
                    "listing_id": listing_id,
                    "listing_title": listing_title,
                    "constraint": constraint,
                    "query_text": result.get("query_text"),
                    "value": result.get("value"),
                    "reason": result.get("reason"),
                    "evidence": result.get("evidence", []),
                }
            )

    return statuses

async def orchestrate_search(
    user_text: str,
    intent: Dict[str, Any],
    top_n: int = MAX_ITEMS_DEFAULT,
    fallback_top_k: int = 5,
    max_items: int = MAX_ITEMS_DEFAULT,
    source: Source = "fixtures",
) -> Dict[str, Any]:
    """High-level search orchestration tool (fixtures + apify)."""
    if max_items > MAX_ITEMS_HARD_CAP:
        return {
            "need_clarification": True,
            "questions": [f"Too many items requested ({max_items}). Please use <= {MAX_ITEMS_HARD_CAP}."],
        }

    intent_obj, dropped_requests = await _validate_and_repair_intent(intent, attempts=2)
    # 🔴 BACKWARD COMPATIBILITY BRIDGE
    # If intent came in legacy format (must_have_fields, etc.),
    # but constraints are empty → reconstruct constraints
    if not intent_obj.constraints:
        legacy_req = SearchRequest(
            city=intent_obj.city,
            check_in=intent_obj.check_in,
            check_out=intent_obj.check_out,
            nights=intent_obj.nights,
            adults=intent_obj.adults or 2,
            children=intent_obj.children or 0,
            rooms=intent_obj.rooms or 1,
            must_have_fields=intent.get("must_have_fields", []),
            nice_to_have_fields=intent.get("nice_to_have_fields", []),
            forbidden_fields=intent.get("forbidden_fields", []),
            unknown_requests=intent.get("unknown_requests", []),
            filters=intent_obj.filters,
            property_types=intent_obj.property_types or None,
            occupancy_types=intent_obj.occupancy_types or None,
        )

        intent_obj = intent_obj.model_copy(
            update={"constraints": build_constraints_from_legacy_state(legacy_req)}
        )

    resolved = resolve_required_search_context(intent_obj)

    if resolved.need_clarification:
        return {
            "need_clarification": True,
            "questions": resolved.questions,
            "dropped_requests": dropped_requests,
        }

    req = _build_request(
        user_text=user_text,
        intent_obj=intent_obj,
        city=resolved.city,
        check_in=resolved.check_in,
        check_out=resolved.check_out,
    )

    # 1) Retrieve candidates (Apify строго 1 раз / fixtures — просто читаем файл)
    try:
        listings = await get_candidates(req, max_items=max_items, source=source)
    except NotImplementedError:
        return {
            "need_clarification": True,
            "questions": ["Apify retriever is not enabled yet. Using fixtures only for now."],
        }

    # 2) Fixtures safety: fixtures могут не иметь поля city вообще.
    # Тогда фильтруем по явному упоминанию города в name/description/url.
    if source == "fixtures" and req.city:
        city_norm = req.city.strip().lower()

        def _fixture_mentions_city(lst: ListingRaw) -> bool:
            chunks = [
                getattr(lst, "name", "") or "",
                getattr(lst, "description", "") or "",
                getattr(lst, "url", "") or "",
            ]
            text = " ".join(chunks).lower()
            return city_norm in text

        listings = [lst for lst in listings if _fixture_mentions_city(lst)]

    # 3) Dates safety (особенно для fixtures)
    listings = [lst for lst in listings if _covers_dates(lst, req.check_in, req.check_out)]
        # 3.5) Occupancy safety
    occupancy_results = {
        getattr(lst, "id", None) or getattr(lst, "url", None) or str(i): evaluate_occupancy(lst, req)
        for i, lst in enumerate(listings)
    }

    filtered_listings = []
    for i, lst in enumerate(listings):
        key = getattr(lst, "id", None) or getattr(lst, "url", None) or str(i)
        occ = occupancy_results[key]
        if occ.passed:
            filtered_listings.append(lst)

    listings = filtered_listings

    # 4) No candidates after filters → ask to change dates / clarify
    if not listings:
        return {
            "need_clarification": True,
            "questions": ["Ничего не найдено по текущим условиям. Попробуй изменить требования."],
        }

    # 5) Structured ranking + fallback on top-K for UNCERTAIN must-have fields
    ranked = _rank_structured(req, listings)
    await _apply_fallback_topk(req, ranked, fallback_top_k=fallback_top_k)
    ranked = await _attach_unknown_request_results(req, ranked)    # 6) Strict must-have filter AFTER fallback too
    ranked = [
        it
        for it in ranked
        if not _fails_must(it["matches"], req.must_have_fields)
        and not _fails_numeric_filters(it.get("numeric_results"))
    ]
    ranked.sort(key=lambda x: x["score"], reverse=True)
    normalized = normalize_search_response(
        req,
        ranked,
        top_n=top_n,
        dropped_requests=dropped_requests,
    )

    payload = normalized.model_dump(mode="json", exclude_none=True)
    payload["constraint_statuses"] = _build_constraint_statuses(ranked[: max(0, top_n)])
    return payload
    
def _format_match_why(field: Field, fm: Any) -> str:
    if fm is None:
        return f"{field.name}: missing match"

    if fm.value == Ternary.YES:
        if fm.evidence and fm.evidence[0].snippet:
            return f"{field.name}: {fm.evidence[0].snippet}"
        return f"{field.name}: matched"

    if fm.value == Ternary.UNCERTAIN:
        return f"{field.name}: maybe (needs check)"

    return f"{field.name}: not found"


def _score_listing(
    req: SearchRequest,
    matches: dict[Field, Any],
    numeric_results: List[Any] | None = None,
) -> Tuple[float, int, int, List[str]]:
    """MVP scoring.

    Amenities:
    - must-have YES: +10
    - must-have UNCERTAIN: +3
    - must-have NO: -100
    - nice-to-have YES: +1

    Numeric filters:
    - YES: +10
    - UNCERTAIN: +3
    - NO: -100
    """
    score = 0.0
    why: List[str] = []

    must_total = len(req.must_have_fields or [])
    must_yes = 0

    for f in (req.must_have_fields or []):
        fm = matches.get(f)

        if fm is None:
            why.append(_format_match_why(f, fm))
            continue

        if fm.value == Ternary.YES:
            score += 10
            must_yes += 1
        elif fm.value == Ternary.UNCERTAIN:
            score += 3
        else:
            score -= 100

        why.append(_format_match_why(f, fm))

    for f in (req.nice_to_have_fields or []):
        fm = matches.get(f)
        if fm and fm.value == Ternary.YES:
            score += 1
            if fm.evidence and fm.evidence[0].snippet:
                why.append(f"+ {f.name}: {fm.evidence[0].snippet}")
            else:
                why.append(f"+ {f.name}: matched")

    for nr in (numeric_results or []):
        if nr.value == Ternary.YES:
            score += 10
        elif nr.value == Ternary.UNCERTAIN:
            score += 3
        else:
            score -= 100

        why.append(nr.why)

    return score, must_yes, must_total, why
