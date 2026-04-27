def extract_listing_ids(items: list[dict]) -> list[str]:
    return [item.get("listing_id") for item in items]


def has_ineligible_leak(
    predicted_ids: list[str],
    expected_eligibility: dict[str, str],
) -> bool:
    return any(
        expected_eligibility.get(listing_id) == "ineligible"
        for listing_id in predicted_ids
    )


def has_tier_violation(
    predicted_ids: list[str],
    expected_tiers: dict[str, str],
) -> bool:
    tier_rank = {
        "strong": 0,
        "partial": 1,
        "weak": 2,
    }

    predicted_ranks = [
        tier_rank[expected_tiers[listing_id]]
        for listing_id in predicted_ids
        if listing_id in expected_tiers
    ]

    return predicted_ranks != sorted(predicted_ranks)


def compare_case(
    *,
    case: dict,
    predicted_items: list[dict],
) -> dict:
    predicted_ids = extract_listing_ids(predicted_items)
    expected_ids = case["expected_selected_ids"]

    predicted_set = set(predicted_ids)
    expected_set = set(expected_ids)

    return {
        "case_id": case["case_id"],
        "group": case["group"],
        "description": case.get("description", ""),
        "top_n": case["top_n"],

        "predicted_ids": predicted_ids,
        "expected_ids": expected_ids,

        "exact_match": predicted_ids == expected_ids,
        "selected_set_match": predicted_set == expected_set,
        "top_1_correct": predicted_ids[:1] == expected_ids[:1],

        "ineligible_leak": has_ineligible_leak(
            predicted_ids=predicted_ids,
            expected_eligibility=case["expected_eligibility"],
        ),

        "tier_violation": has_tier_violation(
            predicted_ids=predicted_ids,
            expected_tiers=case["expected_tiers"],
        ),
    }