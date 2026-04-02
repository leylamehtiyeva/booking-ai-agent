from app.logic.answer_generation import build_user_answer


def test_build_user_answer_for_clarification():
    payload = {
        "need_clarification": True,
        "questions": ["В каком городе искать?"],
        "request_summary": None,
        "results_count": 0,
        "top_results": [],
    }

    out = build_user_answer(payload)

    assert "В каком городе искать?" in out


def test_build_user_answer_for_results():
    payload = {
    "need_clarification": False,
    "questions": [],
    "request_summary": {
        "city": "Baku",
        "check_in": "2026-04-08",
        "check_out": "2026-04-15",
        "must_have_fields": ["kitchen"],
        "nice_to_have_fields": [],
        "property_types": ["apartment"],
        "occupancy_types": [],
        "filters": {},
        "unknown_requests": [],
    },
    "active_intent": {
        "city": "Baku",
        "check_in": "2026-04-08",
        "check_out": "2026-04-15",
        "must_have_fields": ["kitchen"],
        "nice_to_have_fields": [],
        "property_types": ["apartment"],
        "occupancy_types": [],
        "filters": {},
        "unknown_requests": [],
    },
    "results_count": 1,
    "top_results": [
        {
            "result_id": "abc123",
            "title": "Apartment STEL",
            "url": "https://example.com/stel",
            "score": 23.0,
            "matched_must": "1/1",
            "matched_constraints": [
                {
                    "name": "kitchen",
                    "status": "matched",
                    "reason": "Private kitchen",
                }
            ],
            "uncertain_constraints": [
                {
                    "name": "price_total",
                    "status": "uncertain",
                    "reason": "PRICE: currency mismatch listing=USD, request=AZN",
                }
            ],
            "failed_constraints": [],
            "matched_constraint_names": ["kitchen"],
            "uncertain_constraint_names": ["price_total"],
            "failed_constraint_names": [],
            "key_facts": {
                "property_type": "apartment",
                "listing_currency": "USD",
            },
            "fit_summary": "Matches all required criteria.",
            "why_match": ["Private kitchen"],
            "tradeoffs": [],
            "uncertain_points": ["PRICE: currency mismatch listing=USD, request=AZN"],
            "price_summary": None,
            "budget_summary": None,
            "key_facts_summary": "type: apartment",
            "why": [
                "KITCHEN: Private kitchen",
                "PRICE: currency mismatch listing=USD, request=AZN",
            ],
        }
    ],
    "debug_notes": [],
}

    out = build_user_answer(payload)

    assert "I found 1 relevant option(s) in Baku for 2026-04-08 to 2026-04-15." in out
    assert "Apartment STEL" in out
    assert "Overall fit: Matches all required criteria." in out
    assert "Why it matches:" in out
    assert "- Private kitchen" in out
    assert "Link: https://example.com/stel" in out


def test_build_user_answer_for_multiple_questions():
    payload = {
        "need_clarification": True,
        "questions": ["В каком городе искать?", "Какие даты заезда и выезда?"],
        "request_summary": None,
        "results_count": 0,
        "top_results": [],
    }

    out = build_user_answer(payload)

    assert "I need a few more details:" in out
    assert "В каком городе искать?" in out
    assert "Какие даты заезда и выезда?" in out