from app.logic.build_answer_payload import build_answer_payload

from app.schemas.search_response import (
    ConstraintStatus,
    NormalizedRequestSummary,
    NormalizedSearchResponse,
    NormalizedSearchResult,
    ResultFact,
    UnknownFieldEvidence,
    UnknownRequestResult,
)


def test_build_answer_payload_for_normal_results():
    response = NormalizedSearchResponse(
        need_clarification=False,
        questions=[],
        request_summary=NormalizedRequestSummary(
            city="Baku",
            check_in="2026-04-08",
            check_out="2026-04-15",
            must_have_fields=["kitchen"],
            nice_to_have_fields=["balcony"],
            property_types=["apartment"],
            occupancy_types=[],
            filters={
                "bedrooms_min": 2,
                "price": {
                    "max_amount": 120,
                    "currency": "USD",
                    "scope": "per_night",
                },
            },
            unknown_requests=[],
        ),
        results=[
            NormalizedSearchResult(
                result_id="abc123",
                title="Apartment STEL",
                url="https://example.com/stel",
                score=23.0,
                matched_must_count=1,
                matched_must_total=1,
                matched_constraints=[
                    ConstraintStatus(
                        name="kitchen",
                        status="matched",
                        reason="Private kitchen",
                    ),
                    ConstraintStatus(
                        name="property_type",
                        status="matched",
                        reason="PROPERTY_TYPE: matched apartment",
                    ),
                ],
                uncertain_constraints=[
                    ConstraintStatus(
                        name="price_total",
                        status="uncertain",
                        reason="PRICE: currency mismatch listing=USD, request=AZN",
                    )
                ],
                failed_constraints=[],
                facts=[
                    ResultFact(key="property_type", value="apartment", source="property_semantics"),
                    ResultFact(key="listing_price_total", value=493.39, source="listing"),
                    ResultFact(key="listing_currency", value="USD", source="listing"),
                    ResultFact(key="bedrooms", value=2, source="numeric_filters"),
                ],
                why=[
                    "KITCHEN: Private kitchen",
                    "PRICE: currency mismatch listing=USD, request=AZN",
                ],
            )
        ],
        debug_notes=[],
    )

    payload = build_answer_payload(
        response,
        latest_user_query="I want an apartment in Baku with a kitchen",
        top_k=3,
    )

    assert payload["need_clarification"] is False
    assert payload["results_count"] == 1
    assert payload["request_summary"]["city"] == "Baku"
    assert payload["active_intent"]["city"] == "Baku"
    assert payload["latest_user_query"] == "I want an apartment in Baku with a kitchen"

    first = payload["top_results"][0]
    assert first["result_id"] == "abc123"
    assert first["title"] == "Apartment STEL"
    assert first["matched_must"] == "1/1"

    assert "kitchen" in first["matched_constraint_names"]
    assert "price_total" in first["uncertain_constraint_names"]

    assert first["key_facts"]["property_type"] == "apartment"
    assert first["key_facts"]["listing_currency"] == "USD"
    assert first["key_facts"]["bedrooms"] == 2

    assert first["fit_summary"]
    assert "Matches all required criteria" in first["fit_summary"]

    assert first["why_match"]
    assert "Private kitchen" in first["why_match"]

    assert first["uncertain_points"]
    assert "PRICE: currency mismatch listing=USD, request=AZN" in first["uncertain_points"]

    assert first["tradeoffs"] == []

    assert first["price_summary"] == "493.39 USD total"
    assert first["budget_summary"] is None
    assert first["budget_status"] is None

    assert first["key_facts_summary"]
    assert "type: apartment" in first["key_facts_summary"]
    assert "2 bedroom(s)" in first["key_facts_summary"]


def test_build_answer_payload_for_clarification():
    response = NormalizedSearchResponse(
        need_clarification=True,
        questions=["В каком городе искать?"],
        request_summary=None,
        results=[],
        debug_notes=[],
    )

    payload = build_answer_payload(response)

    assert payload["need_clarification"] is True
    assert payload["questions"] == ["В каком городе искать?"]
    assert payload["results_count"] == 0
    assert payload["top_results"] == []
    
    
def test_build_answer_payload_uses_uncertain_reason_instead_of_field_name():
    response = NormalizedSearchResponse(
        need_clarification=False,
        questions=[],
        request_summary=NormalizedRequestSummary(
            city="Baku",
            check_in="2026-04-08",
            check_out="2026-04-15",
            must_have_fields=["pet_friendly", "kitchen"],
            nice_to_have_fields=[],
            property_types=["apartment"],
            occupancy_types=[],
            filters={},
            unknown_requests=[],
        ),
        results=[
            NormalizedSearchResult(
                result_id="apt1",
                title="Test Apartment",
                url="https://example.com/test",
                score=10.0,
                matched_must_count=1,
                matched_must_total=2,
                matched_constraints=[
                    ConstraintStatus(
                        name="kitchen",
                        status="matched",
                        reason="Kitchen",
                    )
                ],
                uncertain_constraints=[
                    ConstraintStatus(
                        name="pet_friendly",
                        status="uncertain",
                        reason="Pet policy is not explicitly confirmed in the listing.",
                    )
                ],
                failed_constraints=[],
                facts=[],
                why=["PET_FRIENDLY: maybe (needs check)", "KITCHEN: Kitchen"],
            )
        ],
        debug_notes=[],
    )

    payload = build_answer_payload(response, top_k=3)
    first = payload["top_results"][0]

    assert first["uncertain_points"] == [
        "Pet policy is not explicitly confirmed in the listing."
    ]
    
    
def test_build_answer_payload_includes_unknown_request_points():
    response = NormalizedSearchResponse(
        need_clarification=False,
        questions=[],
        request_summary=NormalizedRequestSummary(
            city="Baku",
            check_in="2026-04-08",
            check_out="2026-04-15",
            must_have_fields=["iron"],
            nice_to_have_fields=[],
            property_types=["apartment"],
            occupancy_types=[],
            filters={},
            unknown_requests=["satellite TV"],
        ),
        results=[
            NormalizedSearchResult(
                result_id="apt1",
                title="Compact Apartment",
                url="https://example.com/compact",
                score=10.0,
                matched_must_count=1,
                matched_must_total=1,
                matched_constraints=[
                    ConstraintStatus(
                        name="iron",
                        status="matched",
                        reason="Ironing facilities",
                    )
                ],
                uncertain_constraints=[],
                failed_constraints=[],
                unknown_request_results=[
                    UnknownRequestResult(
                        query_text="satellite TV",
                        value="FOUND",
                        reason="The listing description mentions satellite channels.",
                        evidence=[
                            UnknownFieldEvidence(
                                source_path="listing.description",
                                snippet="and have satellite channels",
                            )
                        ],
                    )
                ],
                facts=[],
                why=[],
            )
        ],
        debug_notes=[],
    )

    payload = build_answer_payload(response, top_k=3)
    first = payload["top_results"][0]

    assert "unknown_request_results" in first
    assert first["unknown_request_results"]
    assert first["unknown_request_results"][0]["query_text"] == "satellite TV"
    assert first["unknown_request_points"] == [
        "The listing description mentions satellite channels."
    ]
    
    
def test_build_answer_payload_includes_ranking_reasons_and_standout_reason():
    response = NormalizedSearchResponse(
        need_clarification=False,
        questions=[],
        request_summary=NormalizedRequestSummary(
            city="Baku",
            check_in="2026-04-08",
            check_out="2026-04-15",
            must_have_fields=["iron"],
            nice_to_have_fields=[],
            property_types=["apartment"],
            occupancy_types=[],
            filters={},
            unknown_requests=["satellite TV"],
        ),
        results=[
            NormalizedSearchResult(
                result_id="apt1",
                title="Compact Apartment",
                url="https://example.com/compact",
                score=10.0,
                matched_must_count=1,
                matched_must_total=1,
                matched_constraints=[
                    ConstraintStatus(
                        name="iron",
                        status="matched",
                        reason="Ironing facilities",
                    )
                ],
                uncertain_constraints=[],
                failed_constraints=[],
                unknown_request_results=[
                    UnknownRequestResult(
                        query_text="satellite TV",
                        value="FOUND",
                        reason="The listing description mentions satellite channels.",
                        evidence=[
                            UnknownFieldEvidence(
                                source_path="listing.description",
                                snippet="and have satellite channels",
                            )
                        ],
                    )
                ],
                facts=[],
                why=[
                    "UNKNOWN_MATCH: satellite TV found",
                    "PROPERTY_TYPE: matched apartment",
                ],
            )
        ],
        debug_notes=[],
    )

    payload = build_answer_payload(response, top_k=3)
    first = payload["top_results"][0]

    assert first["ranking_reasons"]
    assert "satellite TV found" in first["ranking_reasons"][0]
    assert first["standout_reason"] == "The only option that explicitly matches your requested detail: satellite TV"