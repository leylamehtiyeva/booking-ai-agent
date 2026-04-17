from __future__ import annotations

from typing import Any

from app.schemas.search_response import NormalizedSearchResponse


IMPORTANT_FACT_KEYS = {
    "property_type",
    "occupancy_type",
    "bedrooms",
    "bathrooms",
    "area_sqm",
    "price_total",
    "price_per_night",
    "listing_price_total",
    "listing_price_per_night_derived",
    "listing_currency",
    "night_count",
    "budget_total_derived",
    "budget_currency",
    "budget_scope",
}




def _fact_list_to_dict(facts: list[Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for fact in facts or []:
        key = getattr(fact, "key", None)
        value = getattr(fact, "value", None)
        if key is None:
            continue
        if key in IMPORTANT_FACT_KEYS:
            out[key] = value
    return out


def _constraint_names(items: list[Any]) -> list[str]:
    out: list[str] = []
    for item in items or []:
        name = getattr(item, "name", None)
        if name:
            out.append(name)
    return out


def _constraint_details(items: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items or []:
        out.append(
            {
                "name": getattr(item, "name", None),
                "status": getattr(item, "status", None),
                "reason": getattr(item, "reason", None),
            }
        )
    return out

def _requested_constraint_details(active_intent: dict[str, Any] | None) -> list[dict[str, Any]]:
    constraints = (active_intent or {}).get("constraints") or []
    out: list[dict[str, Any]] = []

    for c in constraints:
        if isinstance(c, dict):
            out.append(
                {
                    "raw_text": c.get("raw_text"),
                    "normalized_text": c.get("normalized_text"),
                    "priority": c.get("priority"),
                    "category": c.get("category"),
                    "mapping_status": c.get("mapping_status"),
                    "mapped_fields": list(c.get("mapped_fields") or []),
                    "evidence_strategy": c.get("evidence_strategy"),
                }
            )
    return out


def _normalize_constraint_key(value: str | None) -> str:
    if not value:
        return ""

    return (
        str(value)
        .strip()
        .casefold()
        .replace("-", "_")
        .replace(" ", "_")
    )


def _build_requested_constraint_lookup(
    active_intent: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    constraints = (active_intent or {}).get("constraints") or []
    lookup: dict[str, dict[str, Any]] = {}

    for c in constraints:
        if not isinstance(c, dict):
            continue

        payload = {
            "raw_text": c.get("raw_text"),
            "normalized_text": c.get("normalized_text"),
            "priority": c.get("priority"),
            "category": c.get("category"),
            "mapping_status": c.get("mapping_status"),
            "mapped_fields": list(c.get("mapped_fields") or []),
            "evidence_strategy": c.get("evidence_strategy"),
        }

        aliases = {
            _normalize_constraint_key(c.get("normalized_text")),
            _normalize_constraint_key(c.get("raw_text")),
        }

        for field_name in (c.get("mapped_fields") or []):
            aliases.add(_normalize_constraint_key(str(field_name)))

        for alias in aliases:
            if alias:
                lookup[alias] = payload

    return lookup


def _lookup_requested_constraint(
    name: str | None,
    requested_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    key = _normalize_constraint_key(name)
    if not key:
        return None
    return requested_lookup.get(key)


def _is_uncertain_reason(text: str | None) -> bool:
    if not text:
        return False

    lowered = str(text).strip().casefold()

    markers = [
        "not explicitly confirmed",
        "needs confirmation",
        "no mention",
        "not mentioned",
        "uncertain",
        "maybe",
        "needs check",
    ]
    return any(marker in lowered for marker in markers)


def _candidate(score: int, text: str | None) -> tuple[int, str] | None:
    if not text:
        return None
    value = str(text).strip()
    if not value:
        return None
    return (score, value)

def _pick_reason_lines(items: list[dict[str, Any]], limit: int = 4) -> list[str]:
    out: list[str] = []
    for item in items or []:
        reason = item.get("reason")
        name = item.get("name")
        if reason:
            out.append(str(reason))
        elif name:
            out.append(str(name))
        if len(out) >= limit:
            break
    return out


def _build_price_summary(facts: dict[str, Any]) -> str | None:
    currency = facts.get("listing_currency")

    total_price = facts.get("listing_price_total")
    per_night = facts.get("listing_price_per_night_derived")
    night_count = facts.get("night_count")

    if total_price is not None and currency and night_count:
        return f"{total_price} {currency} total for {night_count} night(s)"
    if total_price is not None and currency:
        return f"{total_price} {currency} total"
    if per_night is not None and currency:
        return f"{per_night} {currency} per night"
    return None


def _build_budget_summary(facts: dict[str, Any]) -> tuple[str | None, str | None]:
    budget_total = facts.get("budget_total_derived")
    budget_currency = facts.get("budget_currency")
    listing_total = facts.get("listing_price_total")

    if budget_total is None or budget_currency is None or listing_total is None:
        return None, None

    if float(listing_total) <= float(budget_total):
        return (
            f"Within your budget of {budget_total} {budget_currency}",
            "within_budget",
        )
    return (
        f"Above your budget of {budget_total} {budget_currency}",
        "over_budget",
    )


def _build_fit_summary(
    matched_details: list[dict[str, Any]],
    failed_details: list[dict[str, Any]],
    uncertain_details: list[dict[str, Any]],
    budget_summary: str | None,
) -> str:
    parts: list[str] = []

    if failed_details:
        parts.append("Some requested constraints are not satisfied")
    elif uncertain_details:
        parts.append("Some requested details are still uncertain")
    elif matched_details:
        parts.append("Looks like a relevant match")

    if budget_summary:
        parts.append(budget_summary)

    return ". ".join(parts) + ("." if parts else "")


def _build_key_facts_summary(facts: dict[str, Any]) -> str | None:
    parts: list[str] = []

    if facts.get("property_type"):
        parts.append(f"type: {facts['property_type']}")
    if facts.get("occupancy_type"):
        parts.append(f"occupancy: {facts['occupancy_type']}")
    if facts.get("bedrooms") is not None:
        parts.append(f"{facts['bedrooms']} bedroom(s)")
    if facts.get("bathrooms") is not None:
        parts.append(f"{facts['bathrooms']} bathroom(s)")
    if facts.get("area_sqm") is not None:
        parts.append(f"{facts['area_sqm']} sqm")

    price_summary = _build_price_summary(facts)
    if price_summary:
        parts.append(price_summary)

    if not parts:
        return None
    return ", ".join(parts)

def _build_ranking_reasons(result: dict[str, Any]) -> list[str]:
    reasons: list[str] = []

    for line in result.get("why") or []:
        if not line:
            continue

        text = str(line)

        if text.startswith("UNKNOWN_MATCH:"):
            reasons.append(text.replace("UNKNOWN_MATCH:", "").strip())
        elif text.startswith("PRICE:"):
            reasons.append(text)
        elif text.startswith("AREA:"):
            reasons.append(text)
        elif text.startswith("BEDROOMS:"):
            reasons.append(text)
        elif text.startswith("PROPERTY_TYPE:"):
            reasons.append(text)
        elif text.startswith("OCCUPANCY_TYPE:"):
            reasons.append(text)

    return reasons[:4]


def _build_standout_reason(
    *,
    matched_details: list[dict[str, Any]],
    uncertain_details: list[dict[str, Any]],
    constraint_resolution_results: list[Any],
    why_match: list[str],
    tradeoffs: list[str],
    uncertain_points: list[str],
    ranking_reasons: list[str],
    budget_summary: str | None,
    budget_status: str | None,
    active_intent: dict[str, Any] | None,
) -> str | None:
    requested_lookup = _build_requested_constraint_lookup(active_intent)
    candidates: list[tuple[int, str]] = []

    # 1) Explicit matched MUST constraints from final normalized matched buckets.
    for item in matched_details or []:
        name = item.get("name")
        reason = item.get("reason")
        requested = _lookup_requested_constraint(name, requested_lookup)

        if requested and requested.get("priority") == "must":
            category = requested.get("category")
            score = 100

            if category == "location":
                score = 110
            elif category == "layout":
                score = 105
            elif category == "policy":
                score = 100

            if reason and not _is_uncertain_reason(reason):
                candidate = _candidate(score, reason)
                if candidate:
                    candidates.append(candidate)
            elif name:
                candidate = _candidate(score - 5, f"The listing confirms: {name}")
                if candidate:
                    candidates.append(candidate)

    # 2) Strong structured positives: budget / ranking reasons.
    if budget_status == "within_budget" and budget_summary:
        candidate = _candidate(95, budget_summary)
        if candidate:
            candidates.append(candidate)

    for line in ranking_reasons or []:
        if not line or _is_uncertain_reason(line):
            continue

        text = str(line)

        if text.startswith("BEDROOMS:"):
            candidate = _candidate(92, text)
        elif text.startswith("PRICE:"):
            candidate = _candidate(91, text)
        elif text.startswith("PROPERTY_TYPE:"):
            candidate = _candidate(90, text)
        elif text.startswith("OCCUPANCY_TYPE:"):
            candidate = _candidate(88, text)
        elif text.startswith("AREA:"):
            candidate = _candidate(87, text)
        else:
            candidate = _candidate(80, text)

        if candidate:
            candidates.append(candidate)

    # 3) Positive fallback confirmations only.
    for item in constraint_resolution_results or []:
        if isinstance(item, dict):
            decision = item.get("decision")
            label = item.get("normalized_text")
            reason = item.get("reason")
        else:
            decision = getattr(item, "decision", None)
            label = getattr(item, "normalized_text", None)
            reason = getattr(item, "reason", None)

        if decision == "YES":
            if reason and not _is_uncertain_reason(reason):
                candidate = _candidate(85, reason)
                if candidate:
                    candidates.append(candidate)
            elif label:
                candidate = _candidate(83, f"The listing explicitly confirms: {label}")
                if candidate:
                    candidates.append(candidate)

    # 4) Generic positive matched reasons.
    for line in why_match or []:
        if not line or _is_uncertain_reason(line):
            continue
        candidate = _candidate(70, line)
        if candidate:
            candidates.append(candidate)

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    # 5) Only if nothing better exists, allow uncertain reason.
    for line in uncertain_points or []:
        candidate = _candidate(10, line)
        if candidate:
            return candidate[1]

    if not tradeoffs and not uncertain_details:
        return "Strong overall match"

    return None

def build_answer_payload(
    response: NormalizedSearchResponse,
    *,
    latest_user_query: str | None = None,
    top_k: int = 3,
) -> dict[str, Any]:
    """
    Build compact answer-generation payload.

    Source of truth:
    - active_intent / request_summary
    - normalized result facts and constraint buckets

    latest_user_query is included only as conversational context.
    """
    request_summary = (
        response.request_summary.model_dump(mode="json", exclude_none=True)
        if response.request_summary
        else None
    )

    if response.need_clarification:
        return {
            "need_clarification": True,
            "questions": list(response.questions or []),
            "latest_user_query": latest_user_query,
            "request_summary": request_summary,
            "active_intent": request_summary,
            "results_count": 0,
            "top_results": [],
            "debug_notes": list(response.debug_notes or []),
        }

    top_results: list[dict[str, Any]] = []

    for r in (response.results or [])[: max(0, top_k)]:
        facts_dict = _fact_list_to_dict(r.facts)

        matched_details = _constraint_details(r.matched_constraints)
        uncertain_details = _constraint_details(r.uncertain_constraints)
        failed_details = _constraint_details(r.failed_constraints)
        matched_requested_details = _constraint_details(r.matched_requested_constraints)
        uncertain_requested_details = _constraint_details(r.uncertain_requested_constraints)
        failed_requested_details = _constraint_details(r.failed_requested_constraints)

        matched_derived_details = _constraint_details(r.matched_derived_matches)
        uncertain_derived_details = _constraint_details(r.uncertain_derived_matches)
        failed_derived_details = _constraint_details(r.failed_derived_matches)
        

        price_summary = _build_price_summary(facts_dict)
        budget_summary, budget_status = _build_budget_summary(facts_dict)

        fit_summary = _build_fit_summary(
            matched_details,
            failed_details,
            uncertain_details,
            budget_summary,
        )
        key_facts_summary = _build_key_facts_summary(facts_dict)

        why_match = _pick_reason_lines(matched_details, limit=4)
        tradeoffs = _pick_reason_lines(failed_details, limit=4)
        uncertain_points = _pick_reason_lines(uncertain_details, limit=4)

        if not why_match and r.why:
            why_match = [str(x) for x in (r.why or [])[:3]]

        ranking_reasons = _build_ranking_reasons(
            {
                "why": list(r.why or []),
            }
        )

        constraint_resolution_results = [
            c.model_dump(mode="json") if hasattr(c, "model_dump") else c
            for c in (r.constraint_resolution_results or [])
        ]

        unresolved_constraint_points = _pick_reason_lines(uncertain_details, limit=4)

        # For future user answer 
        # standout_reason = _build_standout_reason(
        #     matched_details=matched_details,
        #     uncertain_details=uncertain_details,
        #     constraint_resolution_results=constraint_resolution_results,
        #     why_match=why_match,
        #     tradeoffs=tradeoffs,
        #     uncertain_points=uncertain_points,
        #     ranking_reasons=ranking_reasons,
        #     budget_summary=budget_summary,
        #     budget_status=budget_status,
        #     active_intent=request_summary,
        # )
        standout_reason = None

        top_results.append(
            {
                "result_id": r.result_id,
                "title": r.title,
                "url": r.url,
                "score": r.score,
                "matched_constraints": matched_details,
                "uncertain_constraints": uncertain_details,
                "failed_constraints": failed_details,
                "matched_requested_constraints": matched_requested_details,
                "uncertain_requested_constraints": uncertain_requested_details,
                "failed_requested_constraints": failed_requested_details,
                "matched_derived_matches": matched_derived_details,
                "uncertain_derived_matches": uncertain_derived_details,
                "failed_derived_matches": failed_derived_details,
                "matched_constraint_names": _constraint_names(r.matched_constraints),
                "uncertain_constraint_names": _constraint_names(r.uncertain_constraints),
                "failed_constraint_names": _constraint_names(r.failed_constraints),
                "key_facts": facts_dict,
                "unresolved_constraint_points": unresolved_constraint_points,
                "requested_constraints": _requested_constraint_details(request_summary),
                "ranking_reasons": ranking_reasons,
                "standout_reason": standout_reason,
                "key_facts_summary": key_facts_summary,
                "fit_summary": fit_summary,
                "why_match": why_match,
                "tradeoffs": tradeoffs,
                "uncertain_points": uncertain_points,
                "price_summary": price_summary,
                "budget_summary": budget_summary,
                "budget_status": budget_status,
                "why": list(r.why or []),
                "eligibility_status": r.eligibility_status,
                "match_tier": r.match_tier,
                "selection_reasons": list(r.selection_reasons or []),
                "blocking_reasons": list(r.blocking_reasons or []),
                "constraint_resolution_results": constraint_resolution_results,
                "debug_selection": {
                    "score": r.score,
                    "eligibility_status": r.eligibility_status,
                    "match_tier": r.match_tier,
                    "selection_reasons": list(r.selection_reasons or []),
                    "blocking_reasons": list(r.blocking_reasons or []),
                    "matched_constraints": [c.model_dump(mode="json") for c in (r.matched_constraints or [])],
                    "uncertain_constraints": [c.model_dump(mode="json") for c in (r.uncertain_constraints or [])],
                    "failed_constraints": [c.model_dump(mode="json") for c in (r.failed_constraints or [])],
                    "constraint_resolution_results": constraint_resolution_results,
                    "why": list(r.why or []),
                },
            }
        )
    return {
        "need_clarification": False,
        "questions": [],
        "latest_user_query": latest_user_query,
        "request_summary": request_summary,
        "active_intent": request_summary,
        "results_count": len(response.results or []),
        "top_results": top_results,
        "debug_notes": list(response.debug_notes or []),
    }