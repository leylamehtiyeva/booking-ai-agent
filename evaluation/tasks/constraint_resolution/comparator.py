from __future__ import annotations

from typing import Any

from evaluation.tasks.constraint_resolution.dataset import ConstraintResolutionEvalCase


def compare_case(
    *,
    case: ConstraintResolutionEvalCase,
    prediction: dict[str, Any],
) -> dict[str, Any]:
    predicted_decision = prediction.get("decision", "UNCERTAIN")
    expected_decision = case.expected_decision

    predicted_explicit_negative = bool(prediction.get("explicit_negative", False))
    expected_explicit_negative = case.expected_explicit_negative

    return {
        "case_id": case.case_id,
        "case_type": case.case_type,
        "difficulty": case.difficulty,

        "constraint": case.constraint.model_dump(mode="json"),
        "listing_evidence": [
            evidence.model_dump(mode="json")
            for evidence in case.listing_evidence
        ],

        "expected_decision": expected_decision,
        "predicted_decision": predicted_decision,
        "decision_correct": predicted_decision == expected_decision,

        "expected_explicit_negative": expected_explicit_negative,
        "predicted_explicit_negative": predicted_explicit_negative,
        "explicit_negative_correct": predicted_explicit_negative == expected_explicit_negative,

        "expected_explanation": case.explanation,

        "prediction_reason": prediction.get("reason", ""),
        "prediction_evidence": prediction.get("evidence", []),
        "raw_prediction": prediction,
    }