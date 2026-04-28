from __future__ import annotations

from collections import defaultdict


LABELS = ["YES", "NO", "UNCERTAIN"]


def safe_divide(num: int | float, denom: int | float) -> float:
    if denom == 0:
        return 0.0
    return num / denom


def compute_confusion_matrix(results: list[dict]) -> dict:
    matrix = {
        expected: {predicted: 0 for predicted in LABELS}
        for expected in LABELS
    }

    for result in results:
        expected = result["expected_decision"]
        predicted = result["predicted_decision"]

        if expected not in matrix:
            matrix[expected] = {}

        if predicted not in matrix[expected]:
            matrix[expected][predicted] = 0

        matrix[expected][predicted] += 1

    return matrix


def compute_label_metrics(results: list[dict]) -> dict:
    metrics = {}

    for label in LABELS:
        tp = sum(
            r["expected_decision"] == label and r["predicted_decision"] == label
            for r in results
        )
        fp = sum(
            r["expected_decision"] != label and r["predicted_decision"] == label
            for r in results
        )
        fn = sum(
            r["expected_decision"] == label and r["predicted_decision"] != label
            for r in results
        )

        precision = safe_divide(tp, tp + fp)
        recall = safe_divide(tp, tp + fn)
        f1 = safe_divide(2 * precision * recall, precision + recall)

        metrics[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }

    return metrics


def compute_metrics(results: list[dict]) -> dict:
    total = len(results)

    decision_correct = sum(r["decision_correct"] for r in results)
    explicit_negative_correct = sum(r["explicit_negative_correct"] for r in results)

    critical_no_to_yes = sum(
        r["expected_decision"] == "NO" and r["predicted_decision"] == "YES"
        for r in results
    )

    critical_yes_to_no = sum(
        r["expected_decision"] == "YES" and r["predicted_decision"] == "NO"
        for r in results
    )

    over_conservative = sum(
        r["expected_decision"] == "YES" and r["predicted_decision"] == "UNCERTAIN"
        for r in results
    )

    under_conservative = sum(
        r["expected_decision"] == "UNCERTAIN" and r["predicted_decision"] == "YES"
        for r in results
    )

    return {
        "total_cases": total,
        "accuracy": safe_divide(decision_correct, total),
        "decision_correct_count": decision_correct,

        "explicit_negative_accuracy": safe_divide(explicit_negative_correct, total),
        "explicit_negative_correct_count": explicit_negative_correct,

        "critical_no_to_yes_count": critical_no_to_yes,
        "critical_yes_to_no_count": critical_yes_to_no,
        "over_conservative_yes_to_uncertain_count": over_conservative,
        "under_conservative_uncertain_to_yes_count": under_conservative,

        "confusion_matrix": compute_confusion_matrix(results),
        "label_metrics": compute_label_metrics(results),
    }


def compute_group_metrics(results: list[dict]) -> dict:
    grouped = defaultdict(list)

    for result in results:
        grouped[result["case_type"]].append(result)

    return {
        case_type: compute_metrics(case_results)
        for case_type, case_results in grouped.items()
    }


def get_errors(results: list[dict]) -> list[dict]:
    return [
        result
        for result in results
        if not result["decision_correct"]
    ]