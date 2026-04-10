from __future__ import annotations

from typing import Any, List

from app.logic.result_ids import build_result_id
from app.schemas.match import Ternary
from app.schemas.query import SearchRequest
from app.schemas.search_response import (
    ConstraintStatus,
    NormalizedRequestSummary,
    NormalizedSearchResponse,
    NormalizedSearchResult,
    ResultFact,
    ConstraintResolutionItem
)

FIELD_DISPLAY_NAMES = {
    "kitchen": "Kitchen",
    "private_bathroom": "Private bathroom",
    "pet_friendly": "Pet policy",
    "parking": "Parking",
    "washing_machine": "Washing machine",
    "balcony": "Balcony",
    "elevator": "Elevator",
    "smoking_allowed": "Smoking policy",
    "parties_allowed": "Party / event policy",
}


def default_uncertain_reason(field_name: str | None) -> str:
    if not field_name:
        return "This requirement is not explicitly confirmed in the listing."

    label = FIELD_DISPLAY_NAMES.get(
        field_name,
        field_name.replace("_", " ").capitalize(),
    )

    return f"{label} is not explicitly confirmed in the listing."


def _request_summary(req: SearchRequest, dropped_requests: List[str]) -> NormalizedRequestSummary:
    """
    Build the normalized request summary.

    Contract:
    - constraints remains the canonical semantic state
    - unknown_requests is a compatibility-only derived projection from canonical constraints
    - dropped_requests is separate debug / normalization residue and must not be mixed
      into unknown_requests
    """
    constraints_present = bool(req.constraints)
    derived_unknown_requests = [
            c.normalized_text
            for c in (req.constraints or [])
            if c.priority.value == "must"
            and c.mapping_status.value == "unresolved"
        ]

    # Compatibility fallback for older call paths that may still pass a request with
    # legacy unknown_requests but without lifted constraints.
    #
    # Important:
    # - use fallback only when canonical constraints are absent
    # - if constraints are present, even an empty derived projection must win,
    #   because unknown_requests is only a lossy compatibility view
    if not constraints_present and getattr(req, "unknown_requests", None):
        seen: set[str] = set()
        fallback_unknown_requests: list[str] = []
        for text in req.unknown_requests:
            cleaned = str(text).strip()
            key = cleaned.casefold()
            if not cleaned or key in seen:
                continue
            seen.add(key)
            fallback_unknown_requests.append(cleaned)
        derived_unknown_requests = fallback_unknown_requests

    return NormalizedRequestSummary(
        city=req.city,
        check_in=req.check_in.isoformat() if req.check_in else None,
        check_out=req.check_out.isoformat() if req.check_out else None,
        must_have_fields=[f.value for f in (req.must_have_fields or [])],
        nice_to_have_fields=[f.value for f in (req.nice_to_have_fields or [])],
        property_types=[x.value if hasattr(x, "value") else str(x) for x in (req.property_types or [])],
        occupancy_types=[x.value if hasattr(x, "value") else str(x) for x in (req.occupancy_types or [])],
        filters=req.filters.model_dump() if req.filters else {},
        unknown_requests=derived_unknown_requests,
        dropped_requests=list(dropped_requests or []),
        constraints=[
            {
                "raw_text": c.raw_text,
                "normalized_text": c.normalized_text,
                "priority": c.priority.value,
                "category": c.category.value,
                "mapping_status": c.mapping_status.value,
                "mapped_fields": [f.value for f in c.mapped_fields],
                "evidence_strategy": c.evidence_strategy.value,
            }
            for c in (req.constraints or [])
        ],
    )

def _humanize_constraint_name(name: str | None) -> str:
    if not name:
        return "This requirement"

    mapping = {
        "kitchen": "Kitchen",
        "private_bathroom": "Private bathroom",
        "pet_friendly": "Pet policy",
        "parking": "Parking",
        "washing_machine": "Washing machine",
        "balcony": "Balcony",
        "elevator": "Elevator",
        "smoking_allowed": "Smoking policy",
        "parties_allowed": "Party / event policy",
        "children_allowed": "Child policy",
        "property_type": "Property type",
        "occupancy_type": "Occupancy type",
        "bedrooms": "Bedroom count",
        "bathrooms": "Bathroom count",
        "area_sqm": "Area",
        "price_total": "Price",
    }
    return mapping.get(name, name.replace("_", " ").capitalize())


def _default_uncertain_reason(name: str | None) -> str:
    label = _humanize_constraint_name(name)
    return f"{label} is not explicitly confirmed in the listing."


def _status_bucket(name: str, value: Any, reason: str | None) -> ConstraintStatus:
    final_reason = reason

    if value == "uncertain" and not final_reason:
        final_reason = _default_uncertain_reason(name)

    return ConstraintStatus(
        name=name,
        status=value,
        reason=final_reason,
    )


def _merge_constraint_resolution_statuses(
    item: dict[str, Any],
    matched: list[ConstraintStatus],
    uncertain: list[ConstraintStatus],
    failed: list[ConstraintStatus],
) -> tuple[list[ConstraintStatus], list[ConstraintStatus], list[ConstraintStatus]]:
    resolution_results = item.get("constraint_resolution_results") or []
    if not resolution_results:
        return matched, uncertain, failed

    resolved_names = {
        str(r.get("normalized_text") or "").strip().casefold()
        for r in resolution_results
        if isinstance(r, dict)
    }

    def _keep(statuses: list[ConstraintStatus]) -> list[ConstraintStatus]:
        kept: list[ConstraintStatus] = []
        for s in statuses:
            if s.constraint and s.constraint.get("normalized_text"):
                key = str(s.constraint.get("normalized_text")).strip().casefold()
            else:
                key = str(s.name or "").strip().casefold()

            if key and key in resolved_names:
                continue
            kept.append(s)
        return kept

    matched = _keep(matched)
    uncertain = _keep(uncertain)
    failed = _keep(failed)

    for raw in resolution_results:
        item_obj = ConstraintResolutionItem.model_validate(raw)
        status = ConstraintStatus(
            name=item_obj.normalized_text,
            status=item_obj.resolution_status,
            reason=item_obj.reason,
            constraint={
                "id": item_obj.constraint_id,
                "raw_text": item_obj.raw_text,
                "normalized_text": item_obj.normalized_text,
            },
        )

        if item_obj.resolution_status == "matched":
            matched.append(status)
        elif item_obj.resolution_status == "failed":
            failed.append(status)
        else:
            uncertain.append(status)

    return matched, uncertain, failed


def _collect_constraint_statuses(
    item: dict[str, Any],
) -> tuple[list[ConstraintStatus], list[ConstraintStatus], list[ConstraintStatus]]:
    matched: list[ConstraintStatus] = []
    uncertain: list[ConstraintStatus] = []
    failed: list[ConstraintStatus] = []

    matches = item.get("matches") or {}
    for field, fm in matches.items():
        if fm is None:
            continue

        name = field.value if hasattr(field, "value") else str(field)
        reason = None
        if getattr(fm, "evidence", None):
            ev = fm.evidence[0]
            reason = getattr(ev, "snippet", None) or getattr(fm, "why", None)

        if fm.value == Ternary.YES:
            matched.append(_status_bucket(name, "matched", reason))
        elif fm.value == Ternary.UNCERTAIN:
            uncertain.append(_status_bucket(name, "uncertain", reason))
        else:
            failed.append(_status_bucket(name, "failed", reason))

    for nr in (item.get("numeric_results") or []):
        name = getattr(nr, "attribute", "numeric_constraint")
        reason = getattr(nr, "why", None)

        if nr.value == Ternary.YES:
            matched.append(_status_bucket(name, "matched", reason))
        elif nr.value == Ternary.UNCERTAIN:
            uncertain.append(_status_bucket(name, "uncertain", reason))
        else:
            failed.append(_status_bucket(name, "failed", reason))

    property_result = item.get("property_result")
    if property_result is not None:
        if property_result.value == Ternary.YES:
            matched.append(_status_bucket("property_type", "matched", property_result.why))
        elif property_result.value == Ternary.UNCERTAIN:
            uncertain.append(_status_bucket("property_type", "uncertain", property_result.why))
        else:
            failed.append(_status_bucket("property_type", "failed", property_result.why))

    occupancy_result = item.get("occupancy_result")
    if occupancy_result is not None:
        if occupancy_result.value == Ternary.YES:
            matched.append(_status_bucket("occupancy_type", "matched", occupancy_result.why))
        elif occupancy_result.value == Ternary.UNCERTAIN:
            uncertain.append(_status_bucket("occupancy_type", "uncertain", occupancy_result.why))
        else:
            failed.append(_status_bucket("occupancy_type", "failed", occupancy_result.why))

    return _merge_constraint_resolution_statuses(item, matched, uncertain, failed)

def _collect_facts(item: dict[str, Any], req: SearchRequest) -> list[ResultFact]:
    listing = item.get("listing")
    facts: list[ResultFact] = []

    property_result = item.get("property_result")
    if property_result is not None and getattr(property_result, "actual_value", None) is not None:
        facts.append(
            ResultFact(
                key="property_type",
                value=property_result.actual_value,
                source="property_semantics",
            )
        )

    occupancy_result = item.get("occupancy_result")
    if occupancy_result is not None and getattr(occupancy_result, "actual_value", None) is not None:
        facts.append(
            ResultFact(
                key="occupancy_type",
                value=occupancy_result.actual_value,
                source="property_semantics",
            )
        )

    for nr in (item.get("numeric_results") or []):
        attr = getattr(nr, "attribute", None)
        actual_value = getattr(nr, "actual_value", None)
        if attr is not None and actual_value is not None:
            facts.append(
                ResultFact(
                    key=attr,
                    value=actual_value,
                    source="numeric_filters",
                )
            )

    if req.check_in and req.check_out:
        night_count = (req.check_out - req.check_in).days
        if night_count > 0:
            facts.append(
                ResultFact(
                    key="night_count",
                    value=night_count,
                    source="request",
                )
            )

    if listing is not None:
        price = getattr(listing, "price", None)
        currency = getattr(listing, "currency", None)

        if price is not None:
            facts.append(ResultFact(key="listing_price_total", value=price, source="listing"))
        if currency is not None:
            facts.append(ResultFact(key="listing_currency", value=currency, source="listing"))

        if price is not None and req.check_in and req.check_out:
            night_count = (req.check_out - req.check_in).days
            if night_count > 0:
                facts.append(
                    ResultFact(
                        key="listing_price_per_night_derived",
                        value=round(float(price) / night_count, 2),
                        source="derived",
                    )
                )

    if req.filters and req.filters.price:
        pf = req.filters.price
        if pf.max_amount is not None:
            if pf.scope == "per_night" and req.check_in and req.check_out:
                night_count = (req.check_out - req.check_in).days
                if night_count > 0:
                    facts.append(
                        ResultFact(
                            key="budget_total_derived",
                            value=round(float(pf.max_amount) * night_count, 2),
                            source="derived",
                        )
                    )
            elif pf.scope == "total_stay":
                facts.append(
                    ResultFact(
                        key="budget_total_derived",
                        value=float(pf.max_amount),
                        source="derived",
                    )
                )

        if pf.currency is not None:
            facts.append(
                ResultFact(
                    key="budget_currency",
                    value=pf.currency,
                    source="request",
                )
            )

        if pf.scope is not None:
            facts.append(
                ResultFact(
                    key="budget_scope",
                    value=pf.scope,
                    source="request",
                )
            )

    return facts


def normalize_search_response(
    req: SearchRequest,
    ranked: list[dict[str, Any]],
    *,
    top_n: int,
    dropped_requests: list[str],
    debug_notes: list[str] | None = None,
) -> NormalizedSearchResponse:
    request_summary = _request_summary(req, dropped_requests)
    results: list[NormalizedSearchResult] = []

    for item in ranked[: max(0, top_n)]:
        listing = item.get("listing")
        matched, uncertain, failed = _collect_constraint_statuses(item)
        facts = _collect_facts(item, req)

        results.append(
            NormalizedSearchResult(
                result_id=build_result_id(listing),
                title=item.get("listing_name") or getattr(listing, "name", "Unknown"),
                url=getattr(listing, "url", None),
                score=float(item.get("score", 0.0)),
                unknown_request_results=item.get("unknown_request_results", []),
                constraint_resolution_results=item.get("constraint_resolution_results", []),
                matched_must_count=int(item.get("must_have_matched", 0)),
                matched_must_total=int(item.get("must_have_total", 0)),
                matched_constraints=matched,
                uncertain_constraints=uncertain,
                failed_constraints=failed,
                facts=facts,
                why=item.get("why") or [],
            )
        )

    return NormalizedSearchResponse(
        need_clarification=False,
        questions=[],
        request_summary=request_summary,
        results=results,
        debug_notes=debug_notes or [],
    )