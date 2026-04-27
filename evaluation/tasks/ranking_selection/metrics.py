from collections import defaultdict


def safe_divide(num: int | float, denom: int | float) -> float:
    if denom == 0:
        return 0.0
    return num / denom


def compute_metrics(results: list[dict]) -> dict:
    total = len(results)

    exact_matches = sum(r["exact_match"] for r in results)
    selected_set_matches = sum(r["selected_set_match"] for r in results)
    top_1_correct = sum(r["top_1_correct"] for r in results)

    ineligible_leaks = sum(r["ineligible_leak"] for r in results)
    tier_violations = sum(r["tier_violation"] for r in results)

    return {
        "total_cases": total,

        "exact_match_rate": safe_divide(exact_matches, total),
        "selected_set_match_rate": safe_divide(selected_set_matches, total),
        "top_1_accuracy": safe_divide(top_1_correct, total),

        "ineligible_leak_rate": safe_divide(ineligible_leaks, total),
        "tier_violation_rate": safe_divide(tier_violations, total),

        "exact_match_count": exact_matches,
        "selected_set_match_count": selected_set_matches,
        "top_1_correct_count": top_1_correct,
        "ineligible_leak_count": ineligible_leaks,
        "tier_violation_count": tier_violations,
    }


def compute_group_metrics(results: list[dict]) -> dict:
    grouped = defaultdict(list)

    for result in results:
        grouped[result["group"]].append(result)

    return {
        group: compute_metrics(group_results)
        for group, group_results in grouped.items()
    }