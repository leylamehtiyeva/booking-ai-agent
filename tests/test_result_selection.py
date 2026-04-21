from app.logic.result_selection import classify_ranked_item, select_ranked_items


def test_classify_ranked_item_as_strong_when_all_required_constraints_are_confirmed():
    item = {
        "score": 25.0,
        "matched_must_total": 2,
        "matched_must_count": 2,
        "constraint_resolution_results": [],
        "matches": {},
        "numeric_results": [],
        "property_result": None,
        "occupancy_result": None,
    }

    classified = classify_ranked_item(item)

    assert classified["eligibility_status"] == "eligible"
    assert classified["match_tier"] == "strong"
    assert "all required constraints are confirmed" in classified["selection_reasons"]


def test_classify_ranked_item_as_partial_when_required_constraints_are_uncertain():
    item = {
        "score": 20.0,
        "matched_must_total": 2,
        "matched_must_count": 1,
        "constraint_resolution_results": [
            {
                "normalized_text": "satellite TV",
                "resolution_status": "uncertain",
                "explicit_negative": False,
            }
        ],
        "matches": {},
        "numeric_results": [],
        "property_result": None,
        "occupancy_result": None,
    }

    classified = classify_ranked_item(item)

    assert classified["eligibility_status"] == "eligible"
    assert classified["match_tier"] == "partial"
    assert "some requested constraints are not fully confirmed" in classified["selection_reasons"]


def test_classify_ranked_item_as_ineligible_when_required_constraints_failed():
    item = {
        "score": 18.0,
        "matched_must_total": 1,
        "matched_must_count": 0,
        "constraint_resolution_results": [
            {
                "normalized_text": "satellite TV",
                "resolution_status": "failed",
                "explicit_negative": True,
            }
        ],
        "matches": {},
        "numeric_results": [],
        "property_result": None,
        "occupancy_result": None,
    }

    classified = classify_ranked_item(item)

    assert classified["eligibility_status"] == "ineligible"
    assert classified["match_tier"] == "weak"
    assert "failed required constraints" in classified["blocking_reasons"]


def test_select_ranked_items_prefers_strong_matches_before_partial():
    strong_item = {
        "listing_name": "Strong listing",
        "score": 30.0,
        "matched_must_total": 1,
        "matched_must_count": 1,
        "constraint_resolution_results": [],
        "matches": {},
        "numeric_results": [],
        "property_result": None,
        "occupancy_result": None,
    }

    partial_item = {
        "listing_name": "Partial listing",
        "score": 40.0,
        "matched_must_total": 2,
        "matched_must_count": 1,
        "constraint_resolution_results": [
            {
                "normalized_text": "satellite TV",
                "resolution_status": "uncertain",
                "explicit_negative": False,
            }
        ],
        "matches": {},
        "numeric_results": [],
        "property_result": None,
        "occupancy_result": None,
    }

    selected = select_ranked_items([partial_item, strong_item], top_n=2)

    assert len(selected) == 2
    assert selected[0]["listing_name"] == "Strong listing"
    assert selected[0]["match_tier"] == "strong"
    assert selected[1]["listing_name"] == "Partial listing"
    assert selected[1]["match_tier"] == "partial"