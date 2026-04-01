from app.logic.build_answer_payload import build_answer_payload
from app.schemas.search_response import (
    ConstraintStatus,
    NormalizedRequestSummary,
    NormalizedSearchResponse,
    NormalizedSearchResult,
    ResultFact,
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

    payload = build_answer_payload(response, top_k=3)

    assert payload["need_clarification"] is False
    assert payload["results_count"] == 1
    assert payload["request_summary"]["city"] == "Baku"

    first = payload["top_results"][0]
    assert first["result_id"] == "abc123"
    assert first["title"] == "Apartment STEL"
    assert first["matched_must"] == "1/1"

    assert "kitchen" in first["matched_constraint_names"]
    assert "price_total" in first["uncertain_constraint_names"]

    assert first["key_facts"]["property_type"] == "apartment"
    assert first["key_facts"]["listing_currency"] == "USD"
    assert first["key_facts"]["bedrooms"] == 2
    assert "best_reasons" in first


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
    