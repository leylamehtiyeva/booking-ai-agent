from __future__ import annotations

from typing import Any


def summarize_selection_signals(item: dict[str, Any]) -> dict[str, int]:
    matched_constraints = item.get("matched_constraints") or []
    uncertain_constraints = item.get("uncertain_constraints") or []
    failed_constraints = item.get("failed_constraints") or []

    if not matched_constraints and not uncertain_constraints and not failed_constraints:
        matched_constraints, uncertain_constraints, failed_constraints = _derive_constraint_buckets(item)

    must_total = int(item.get("must_have_total", 0))
    must_matched = int(item.get("must_have_matched", 0))
    must_failed = 0
    must_uncertain = 0

    matched_names = {
        str(c.get("name") if isinstance(c, dict) else getattr(c, "name", "")).strip().casefold()
        for c in matched_constraints
    }
    uncertain_names = {
        str(c.get("name") if isinstance(c, dict) else getattr(c, "name", "")).strip().casefold()
        for c in uncertain_constraints
    }
    failed_names = {
        str(c.get("name") if isinstance(c, dict) else getattr(c, "name", "")).strip().casefold()
        for c in failed_constraints
    }

    unknown_found_count = 0
    unknown_uncertain_count = 0
    explicit_negative_count = 0

    for result in item.get("constraint_resolution_results", []) or []:
        resolution_status = str(result.get("resolution_status", "")).strip().lower()
        explicit_negative = bool(result.get("explicit_negative", False))

        if resolution_status == "matched":
            unknown_found_count += 1
        elif resolution_status == "uncertain":
            unknown_uncertain_count += 1
        elif resolution_status == "failed":
            must_failed += 1

        if explicit_negative:
            explicit_negative_count += 1

    # Count uncertain/failed canonical must constraints
    for name in failed_names:
        if name:
            must_failed += 1

    for name in uncertain_names:
        if name:
            must_uncertain += 1

    return {
        "must_total": must_total,
        "must_matched": must_matched,
        "must_uncertain": must_uncertain,
        "must_failed": must_failed,
        "unknown_found_count": unknown_found_count,
        "unknown_uncertain_count": unknown_uncertain_count,
        "explicit_negative_count": explicit_negative_count,
    }


def classify_ranked_item(item: dict[str, Any]) -> dict[str, Any]:
    signals = summarize_selection_signals(item)

    must_total = signals["must_total"]
    must_matched = signals["must_matched"]
    must_uncertain = signals["must_uncertain"]
    must_failed = signals["must_failed"]
    unknown_uncertain_count = signals["unknown_uncertain_count"]
    explicit_negative_count = signals["explicit_negative_count"]

    selection_reasons: list[str] = []
    blocking_reasons: list[str] = []

    if must_failed > 0:
        blocking_reasons.append("failed required constraints")
    if explicit_negative_count > 0:
        blocking_reasons.append("explicit negative evidence for requested constraints")

    if blocking_reasons:
        eligibility_status = "ineligible"
        match_tier = "weak"
    else:
        eligibility_status = "eligible"

        if must_total > 0 and must_matched == must_total and must_uncertain == 0 and unknown_uncertain_count == 0:
            match_tier = "strong"
            selection_reasons.append("all required constraints are confirmed")
        elif must_failed == 0:
            match_tier = "partial"
            if must_uncertain > 0 or unknown_uncertain_count > 0:
                selection_reasons.append("some requested constraints are not fully confirmed")
            else:
                selection_reasons.append("matches the core request")
        else:
            match_tier = "weak"

    classified = dict(item)
    classified["selection_signals"] = signals
    classified["eligibility_status"] = eligibility_status
    classified["match_tier"] = match_tier
    classified["selection_reasons"] = selection_reasons
    classified["blocking_reasons"] = blocking_reasons
    return classified


def select_ranked_items(items: list[dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
    classified = [classify_ranked_item(item) for item in items]

    strong = [x for x in classified if x.get("eligibility_status") == "eligible" and x.get("match_tier") == "strong"]
    partial = [x for x in classified if x.get("eligibility_status") == "eligible" and x.get("match_tier") == "partial"]

    strong.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
    partial.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)

    selected: list[dict[str, Any]] = []
    selected.extend(strong[: max(0, top_n)])

    remaining = max(0, top_n - len(selected))
    if remaining > 0:
        selected.extend(partial[:remaining])

    return selected


def _derive_constraint_buckets(
    item: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    matched: list[dict[str, Any]] = []
    uncertain: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    matches = item.get("matches") or {}
    for field, fm in matches.items():
        if fm is None:
            continue

        name = field.value if hasattr(field, "value") else str(field)
        ternary_value = getattr(getattr(fm, "value", None), "value", None) or str(getattr(fm, "value", "")).lower()

        status_item = {"name": name}

        if ternary_value == "yes":
            matched.append(status_item)
        elif ternary_value == "uncertain":
            uncertain.append(status_item)
        elif ternary_value == "no":
            failed.append(status_item)

    for result in item.get("numeric_results", []) or []:
        name = str(getattr(result, "attribute", "")).strip()
        ternary_value = getattr(getattr(result, "value", None), "value", None) or str(getattr(result, "value", "")).lower()
        if not name:
            continue

        status_item = {"name": name}

        if ternary_value == "yes":
            matched.append(status_item)
        elif ternary_value == "uncertain":
            uncertain.append(status_item)
        elif ternary_value == "no":
            failed.append(status_item)

    for attr_name in ("property_result", "occupancy_result"):
        result = item.get(attr_name)
        if result is None:
            continue

        name = attr_name.replace("_result", "")
        ternary_value = getattr(getattr(result, "value", None), "value", None) or str(getattr(result, "value", "")).lower()

        status_item = {"name": name}

        if ternary_value == "yes":
            matched.append(status_item)
        elif ternary_value == "uncertain":
            uncertain.append(status_item)
        elif ternary_value == "no":
            failed.append(status_item)

    return matched, uncertain, failed