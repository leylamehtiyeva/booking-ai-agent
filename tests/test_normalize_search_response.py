from datetime import date

from app.logic.normalize_search_response import normalize_search_response
from app.schemas.fields import Field
from app.schemas.filters import PriceConstraint, SearchFilters
from app.schemas.listing import ListingRaw
from app.schemas.match import Evidence, EvidenceSource, FieldMatch, Ternary
from app.logic.numeric_filters import NumericMatchResult
from app.schemas.property_semantics import PropertyType
from app.schemas.query import SearchRequest


class DummyPropertyResult:
    def __init__(self, value, actual_value, why):
        self.value = value
        self.actual_value = actual_value
        self.why = why


def test_normalize_search_response_builds_request_summary_and_results():
    req = SearchRequest(
        user_message="test query",
        city="Baku",
        check_in=date(2026, 4, 8),
        check_out=date(2026, 4, 15),
        adults=2,
        children=0,
        rooms=1,
        currency="USD",
        budget_max=None,
        must_have_fields=[Field.KITCHEN],
        nice_to_have_fields=[Field.BALCONY],
        forbidden_fields=[],
        min_guest_rating=None,
        filters=SearchFilters(
            bedrooms_min=2,
            price=PriceConstraint(
                max_amount=120,
                currency="USD",
                scope="per_night",
            ),
        ),
        property_types=[PropertyType.APARTMENT],
        occupancy_types=[],
    )

    listing = ListingRaw(
        id=None,
        name="Apartment STEL",
        url="https://example.com/stel",
        price=700.0,
        currency="US$",
        rooms=[],
    )

    matches = {
        Field.KITCHEN: FieldMatch(
            value=Ternary.YES,
            confidence=1.0,
            evidence=[
                Evidence(
                    source=EvidenceSource.STRUCTURED,
                    path="rooms[0].facilities[0]",
                    snippet="Private kitchen",
                )
            ],
        ),
        Field.BALCONY: FieldMatch(
            value=Ternary.UNCERTAIN,
            confidence=0.4,
            evidence=[],
        ),
    }

    numeric_results = [
        NumericMatchResult(
            attribute="bedrooms",
            value=Ternary.YES,
            actual_value=2,
            evidence=[],
            why="BEDROOMS: 2 >= required 2",
        ),
        NumericMatchResult(
            attribute="price_total",
            value=Ternary.UNCERTAIN,
            actual_value=700.0,
            evidence=[],
            why="PRICE: currency mismatch listing=USD, request=AZN",
        ),
    ]

    property_result = DummyPropertyResult(
        value=Ternary.YES,
        actual_value="apartment",
        why="PROPERTY_TYPE: matched apartment",
    )

    ranked = [
        {
            "listing_name": "Apartment STEL",
            "listing": listing,
            "matches": matches,
            "numeric_results": numeric_results,
            "property_result": property_result,
            "occupancy_result": None,
            "score": 23.0,
            "must_have_matched": 1,
            "must_have_total": 1,
            "why": [
                "KITCHEN: Private kitchen",
                "BEDROOMS: 2 >= required 2",
                "PRICE: currency mismatch listing=USD, request=AZN",
                "PROPERTY_TYPE: matched apartment",
            ],
        }
    ]

    out = normalize_search_response(
        req,
        ranked,
        top_n=5,
        dropped_requests=[],
    )

    assert out.need_clarification is False
    assert out.request_summary is not None
    assert out.request_summary.city == "Baku"
    assert out.request_summary.must_have_fields == ["kitchen"]
    assert out.request_summary.nice_to_have_fields == ["balcony"]
    assert out.request_summary.property_types == ["apartment"]

    assert len(out.results) == 1
    r0 = out.results[0]

    assert r0.title == "Apartment STEL"
    assert r0.url == "https://example.com/stel"
    assert r0.result_id.startswith("url_")
    assert r0.score == 23.0
    assert r0.matched_must_count == 1
    assert r0.matched_must_total == 1

    matched_names = [x.name for x in r0.matched_constraints]
    uncertain_names = [x.name for x in r0.uncertain_constraints]

    assert "kitchen" in matched_names
    assert "bedrooms" in matched_names
    assert "property_type" in matched_names
    assert "balcony" in uncertain_names
    assert "price_total" in uncertain_names

    fact_keys = [f.key for f in r0.facts]
    assert "property_type" in fact_keys
    assert "bedrooms" in fact_keys
    assert "price_total" in fact_keys or "listing_price_total" in fact_keys
    assert "listing_currency" in fact_keys
    
    assert "property_type" in fact_keys
    assert "night_count" in fact_keys
    assert "budget_total_derived" in fact_keys