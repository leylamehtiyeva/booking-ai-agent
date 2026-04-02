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
    matched_must: str,
    matched_details: list[dict[str, Any]],
    failed_details: list[dict[str, Any]],
    uncertain_details: list[dict[str, Any]],
    budget_summary: str | None,
) -> str:
    parts: list[str] = []

    if matched_must and "/" in matched_must:
        left, right = matched_must.split("/", 1)
        try:
            left_i = int(left)
            right_i = int(right)
            if right_i > 0:
                if left_i == right_i:
                    parts.append("Matches all required criteria")
                else:
                    parts.append(f"Matches {left_i} of {right_i} required criteria")
        except ValueError:
            pass

    if failed_details:
        parts.append("Some requested constraints are not satisfied")
    elif uncertain_details:
        parts.append("Some requested details are still uncertain")

    if budget_summary:
        parts.append(budget_summary)

    if not parts and matched_details:
        parts.append("Looks like a relevant match")

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

    top_results = []
    for r in (response.results or [])[: max(0, top_k)]:
        facts_dict = _fact_list_to_dict(r.facts)

        matched_details = _constraint_details(r.matched_constraints)
        uncertain_details = _constraint_details(r.uncertain_constraints)
        failed_details = _constraint_details(r.failed_constraints)

        price_summary = _build_price_summary(facts_dict)
        budget_summary, budget_status = _build_budget_summary(facts_dict)
        fit_summary = _build_fit_summary(
            f"{r.matched_must_count}/{r.matched_must_total}",
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

        top_results.append(
            {
                "result_id": r.result_id,
                "title": r.title,
                "url": r.url,
                "score": r.score,
                "matched_must": f"{r.matched_must_count}/{r.matched_must_total}",
                "matched_constraints": matched_details,
                "uncertain_constraints": uncertain_details,
                "failed_constraints": failed_details,
                "matched_constraint_names": _constraint_names(r.matched_constraints),
                "uncertain_constraint_names": _constraint_names(r.uncertain_constraints),
                "failed_constraint_names": _constraint_names(r.failed_constraints),
                "key_facts": facts_dict,
                "key_facts_summary": key_facts_summary,
                "fit_summary": fit_summary,
                "why_match": why_match,
                "tradeoffs": tradeoffs,
                "uncertain_points": uncertain_points,
                "price_summary": price_summary,
                "budget_summary": budget_summary,
                "budget_status": budget_status,
                "why": list(r.why or []),
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