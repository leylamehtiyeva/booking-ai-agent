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

def _best_reason_list(result: dict[str, Any], max_items: int = 3) -> list[str]:
    reasons: list[str] = []
    for item in result.get("matched_constraints") or []:
        reason = item.get("reason")
        if reason:
            reasons.append(str(reason))
        if len(reasons) >= max_items:
            break
    return reasons

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


def build_answer_payload(
    response: NormalizedSearchResponse,
    *,
    top_k: int = 3,
) -> dict[str, Any]:
    """
    Build compact LLM-ready context from normalized search response.

    This payload is intended for answer generation, not for raw debugging.
    """
    if response.need_clarification:
        return {
            "need_clarification": True,
            "questions": list(response.questions or []),
            "request_summary": (
                response.request_summary.model_dump(mode="json", exclude_none=True)
                if response.request_summary
                else None
            ),
            "results_count": 0,
            "top_results": [],
        }

    top_results = []
    for r in (response.results or [])[: max(0, top_k)]:
        facts_dict = _fact_list_to_dict(r.facts)
        matched_details = _constraint_details(r.matched_constraints)
        uncertain_details = _constraint_details(r.uncertain_constraints)
        failed_details = _constraint_details(r.failed_constraints)

        best_reasons = []
        for item in matched_details:
            if item.get("reason"):
                best_reasons.append(item["reason"])
            if len(best_reasons) >= 3:
                break

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
                "best_reasons": best_reasons,
                "why": list(r.why or []),
            }
        )

    return {
        "need_clarification": False,
        "questions": [],
        "request_summary": (
            response.request_summary.model_dump(mode="json", exclude_none=True)
            if response.request_summary
            else None
        ),
        "results_count": len(response.results or []),
        "top_results": top_results,
        "debug_notes": list(response.debug_notes or []),
    }