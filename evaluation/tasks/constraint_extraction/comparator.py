from __future__ import annotations

from typing import Any

from evaluation.core.text_normalization import normalize_text

CANONICAL_MAP = {
    # known amenities / policies
    "air conditioning": "air_conditioning",
    "air-conditioner": "air_conditioning",
    "ac": "air_conditioning",
    "wi-fi": "wifi",
    "private bathroom": "private_bathroom",
    "washing machine": "washing_machine",
    "free cancellation": "free_cancellation",

    # known forbidden / policy textual variants
    "no pets allowed": "pet_friendly",
    "pets not allowed": "pet_friendly",
    "pet-friendly": "pet_friendly",

    "no smoking allowed": "smoking_allowed",
    "non-smoking": "smoking_allowed",
    "smoking not allowed": "smoking_allowed",

    "no parties allowed": "parties_allowed",
    "parties not allowed": "parties_allowed",

    # unresolved textual variants
    "quiet": "quiet neighborhood",
    "quiet place": "quiet neighborhood",
    "preferably somewhere quiet": "quiet neighborhood",
    "somewhere quiet": "quiet neighborhood",
    "not noisy": "away from noisy streets",
    "avoid noisy streets": "away from noisy streets",
    "no noisy streets": "away from noisy streets",
    "not in a noisy neighborhood": "away from noisy streets",

    "near the beach": "close to the beach",
    "be near the beach": "close to the beach",

    "not in the city center": "in the city center",
    "not on the first floor": "not on the first floor",
    "nice view from the room": "nice view",
}


def canonicalize_text(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    return CANONICAL_MAP.get(text, text)

def _normalize_mapped_fields(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        out = []
        for item in value:
            norm = canonicalize_text(item)
            if norm:
                out.append(norm)
        return sorted(set(out))
    return []


def _normalize_mapping_status(value: Any) -> str | None:
    if value is None:
        return None
    norm = normalize_text(value)
    return norm or None


def _normalize_evidence_strategy(value: Any) -> str | None:
    if value is None:
        return None
    norm = normalize_text(value)
    return norm or None


def extract_predicted_constraints(intent_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    constraints = intent_result.get("constraints") or []

    out: dict[str, dict[str, Any]] = {}
    for c in constraints:
        name = canonicalize_text(c.get("normalized_text"))
        if not name:
            continue

        out[name] = {
            "priority": c.get("priority"),
            "category": c.get("category"),
            "mapping_status": _normalize_mapping_status(c.get("mapping_status")),
            "mapped_fields": _normalize_mapped_fields(c.get("mapped_fields")),
            "evidence_strategy": _normalize_evidence_strategy(c.get("evidence_strategy")),
        }
    return out


def compare_case(case, intent_result: dict[str, Any]) -> dict[str, Any]:
    gold_constraints = {
        canonicalize_text(c.normalized_text): {
            "priority": c.priority,
            "category": c.category,
            "mapping_status": _normalize_mapping_status(c.mapping_status),
            "mapped_fields": _normalize_mapped_fields(c.mapped_fields),
            "evidence_strategy": _normalize_evidence_strategy(c.evidence_strategy),
        }
        for c in case.expected_constraints
    }

    pred_constraints = extract_predicted_constraints(intent_result)

    gold_names = set(gold_constraints.keys())
    pred_names = set(pred_constraints.keys())

    correct_names = gold_names & pred_names
    missed_names = sorted(gold_names - pred_names)
    extra_names = sorted(pred_names - gold_names)

    matched_rows = []
    for name in sorted(correct_names):
        gold = gold_constraints[name]
        pred = pred_constraints[name]

        gold_priority = gold["priority"]
        pred_priority = pred["priority"]

        gold_category = gold["category"]
        pred_category = pred["category"]

        gold_mapping_status = gold["mapping_status"]
        pred_mapping_status = pred["mapping_status"]

        gold_mapped_fields = gold["mapped_fields"]
        pred_mapped_fields = pred["mapped_fields"]

        gold_evidence_strategy = gold["evidence_strategy"]
        pred_evidence_strategy = pred["evidence_strategy"]

        matched_rows.append(
            {
                "normalized_text": name,
                "gold_priority": gold_priority,
                "pred_priority": pred_priority,
                "priority_correct": gold_priority == pred_priority,
                "gold_category": gold_category,
                "pred_category": pred_category,
                "category_correct": gold_category == pred_category,
                "gold_mapping_status": gold_mapping_status,
                "pred_mapping_status": pred_mapping_status,
                "mapping_status_correct": gold_mapping_status == pred_mapping_status,
                "gold_mapped_fields": gold_mapped_fields,
                "pred_mapped_fields": pred_mapped_fields,
                "mapped_fields_exact_match": gold_mapped_fields == pred_mapped_fields,
                "gold_evidence_strategy": gold_evidence_strategy,
                "pred_evidence_strategy": pred_evidence_strategy,
                "evidence_strategy_correct": gold_evidence_strategy == pred_evidence_strategy,
                "fully_correct_on_matched_constraint": (
                    gold_priority == pred_priority
                    and gold_category == pred_category
                    and gold_mapping_status == pred_mapping_status
                    and gold_mapped_fields == pred_mapped_fields
                    and gold_evidence_strategy == pred_evidence_strategy
                ),
            }
        )

    exact_constraint_set_match = (gold_names == pred_names)

    exact_full_case_match = (
        exact_constraint_set_match
        and len(correct_names) == len(gold_names)
        and all(row["fully_correct_on_matched_constraint"] for row in matched_rows)
    )

    return {
        "case_id": case.case_id,
        "group": case.group,
        "user_message": case.user_message,
        "constraint_extraction": {
            "gold_count": len(gold_names),
            "pred_count": len(pred_names),
            "correct_count": len(correct_names),
            "missed_constraints": missed_names,
            "extra_constraints": extra_names,
            "exact_constraint_set_match": exact_constraint_set_match,
            "exact_full_case_match": exact_full_case_match,
        },
        "matched_rows": matched_rows,
    }