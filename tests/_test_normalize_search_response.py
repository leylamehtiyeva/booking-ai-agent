from datetime import date

from app.logic.normalize_search_response import normalize_search_response
from app.logic.numeric_filters import NumericMatchResult
from app.schemas.constraints import (
    ConstraintCategory,
    ConstraintMappingStatus,
    ConstraintPriority,
    EvidenceStrategy,
    UserConstraint,
)
from app.schemas.fields import Field
from app.schemas.filters import PriceConstraint, SearchFilters
from app.schemas.listing import ListingRaw
from app.schemas.match import Evidence, EvidenceSource, FieldMatch, Ternary
from app.schemas.property_semantics import PropertyType
from app.schemas.query import SearchRequest


class DummyPropertyResult:
    def __init__(self, value, actual_value, why):
        self.value = value
        self.actual_value = actual_value
        self.why = why


def _priority_value(constraint) -> str:
    value = getattr(constraint, "priority", None)
    return str(value).split(".")[-1].lower() if value is not None else ""


def _mapping_status_value(constraint) -> str:
    value = getattr(constraint, "mapping_status", None)
    return str(value).split(".")[-1].lower() if value is not None else ""


def test_normalize_search_response_builds_request_summary_and_results():
    req = SearchRequest(
        city="Baku",
        check_in=date(2026, 4, 8),
        check_out=date(2026, 4, 15),
        adults=2,
        children=0,
        rooms=1,
        currency="USD",
        budget_max=None,
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
        constraints=[
            UserConstraint(
                raw_text="place for cooking",
                normalized_text="kitchen",
                priority=ConstraintPriority.MUST,
                category=ConstraintCategory.AMENITY,
                mapping_status=ConstraintMappingStatus.KNOWN,
                mapped_fields=[Field.KITCHEN],
                evidence_strategy=EvidenceStrategy.STRUCTURED,
            ),
            UserConstraint(
                raw_text="satellite TV",
                normalized_text="satellite TV",
                priority=ConstraintPriority.MUST,
                category=ConstraintCategory.OTHER,
                mapping_status=ConstraintMappingStatus.UNRESOLVED,
                mapped_fields=[],
                evidence_strategy=EvidenceStrategy.TEXTUAL,
            ),
            UserConstraint(
                raw_text="balcony if possible",
                normalized_text="balcony if possible",
                priority=ConstraintPriority.NICE,
                category=ConstraintCategory.AMENITY,
                mapping_status=ConstraintMappingStatus.UNRESOLVED,
                mapped_fields=[],
                evidence_strategy=EvidenceStrategy.TEXTUAL,
            ),
        ],
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
        dropped_requests=["legacy parse residue"],
    )

    assert out.need_clarification is False
    assert out.request_summary is not None
    assert out.request_summary.city == "Baku"
    assert out.request_summary.property_types == ["apartment"]

    constraints = out.request_summary.constraints
    must_constraints = [c for c in constraints if c["priority"] == "must"]
    nice_constraints = [c for c in constraints if c["priority"] == "nice"]

    unresolved_must = [
        c
        for c in constraints
        if c["priority"] == "must" and c["mapping_status"] == "unresolved"
    ]

    assert any(c["normalized_text"] == "kitchen" for c in must_constraints)
    assert any("balcony" in c["normalized_text"] for c in nice_constraints)
    assert any(c["normalized_text"] == "satellite TV" for c in unresolved_must)

    assert out.request_summary.dropped_requests == ["legacy parse residue"]

    assert len(out.results) == 1
    r0 = out.results[0]

    assert r0.title == "Apartment STEL"
    assert r0.url == "https://example.com/stel"
    assert r0.result_id.startswith("url_")
    assert r0.score == 23.0

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
    assert "night_count" in fact_keys
    assert "budget_total_derived" in fact_keys


def test_request_summary_keeps_constraints_empty_when_no_constraints_exist():
    req = SearchRequest(
        city="Baku",
        check_in=date(2026, 4, 8),
        check_out=date(2026, 4, 15),
        constraints=[],
    )

    out = normalize_search_response(
        req,
        ranked=[],
        top_n=5,
        dropped_requests=["dropped item"],
    )

    assert out.request_summary is not None
    assert out.request_summary.constraints == []
    assert out.request_summary.dropped_requests == ["dropped item"]


def test_request_summary_keeps_unresolved_nice_constraints_but_no_unresolved_must_projection():
    req = SearchRequest(
        city="Baku",
        check_in=date(2026, 4, 8),
        check_out=date(2026, 4, 15),
        constraints=[
            UserConstraint(
                raw_text="balcony if possible",
                normalized_text="balcony if possible",
                priority=ConstraintPriority.NICE,
                category=ConstraintCategory.AMENITY,
                mapping_status=ConstraintMappingStatus.UNRESOLVED,
                mapped_fields=[],
                evidence_strategy=EvidenceStrategy.TEXTUAL,
            )
        ],
    )

    out = normalize_search_response(
        req,
        ranked=[],
        top_n=5,
        dropped_requests=[],
    )

    assert out.request_summary is not None

    constraints = out.request_summary.constraints
    unresolved_must = [
        c
        for c in constraints
        if _priority_value(c) == "must" and _mapping_status_value(c) == "unresolved"
    ]

    assert unresolved_must == []
    assert len(constraints) == 1
    assert constraints[0]["normalized_text"] == "balcony if possible"


def test_normalize_search_response_merges_constraint_resolution_results():
    req = SearchRequest(
        city="Baku",
        check_in=date(2026, 4, 8),
        check_out=date(2026, 4, 10),
        adults=2,
        children=0,
        rooms=1,
        currency="USD",
        budget_max=None,
        min_guest_rating=None,
        filters=None,
        property_types=[],
        occupancy_types=[],
        constraints=[
            UserConstraint(
                raw_text="place for cooking",
                normalized_text="kitchen",
                priority=ConstraintPriority.MUST,
                category=ConstraintCategory.AMENITY,
                mapping_status=ConstraintMappingStatus.KNOWN,
                mapped_fields=[Field.KITCHEN],
                evidence_strategy=EvidenceStrategy.STRUCTURED,
            ),
            UserConstraint(
                raw_text="satellite TV",
                normalized_text="satellite TV",
                priority=ConstraintPriority.MUST,
                category=ConstraintCategory.OTHER,
                mapping_status=ConstraintMappingStatus.UNRESOLVED,
                mapped_fields=[],
                evidence_strategy=EvidenceStrategy.TEXTUAL,
            ),
        ],
    )

    listing = ListingRaw(
        id="listing-1",
        name="Apartment STEL",
        url="https://example.com/stel",
        price=300.0,
        currency="USD",
        rooms=[],
    )

    matches = {
        Field.KITCHEN: FieldMatch(
            value=Ternary.UNCERTAIN,
            confidence=0.4,
            evidence=[],
        ),
    }

    ranked = [
        {
            "listing_name": "Apartment STEL",
            "listing": listing,
            "matches": matches,
            "numeric_results": [],
            "property_result": None,
            "occupancy_result": None,
            "score": 17.0,
            "why": [],
            "constraint_resolution_results": [
                {
                    "listing_id": "listing-1",
                    "listing_title": "Apartment STEL",
                    "constraint_id": "c-kitchen",
                    "raw_text": "place for cooking",
                    "normalized_text": "kitchen",
                    "resolver_type": "textual",
                    "decision": "YES",
                    "resolution_status": "matched",
                    "confidence": 0.91,
                    "reason": "Kitchen is explicitly supported by listing text.",
                    "evidence": [
                        {
                            "snippet": "Private kitchen",
                            "source": "room_facilities",
                            "path": "rooms[0].facilities",
                        }
                    ],
                    "source_stage": "fallback",
                    "structured_value_before": "UNCERTAIN",
                    "explicit_negative": False,
                },
                {
                    "listing_id": "listing-1",
                    "listing_title": "Apartment STEL",
                    "constraint_id": "c-sat-tv",
                    "raw_text": "satellite TV",
                    "normalized_text": "satellite TV",
                    "resolver_type": "textual",
                    "decision": "UNCERTAIN",
                    "resolution_status": "uncertain",
                    "confidence": 0.3,
                    "reason": "Satellite TV is not explicitly confirmed in the listing.",
                    "evidence": [],
                    "source_stage": "fallback",
                    "structured_value_before": None,
                    "explicit_negative": False,
                },
            ],
        }
    ]

    out = normalize_search_response(
        req,
        ranked,
        top_n=5,
        dropped_requests=[],
    )

    assert len(out.results) == 1
    r0 = out.results[0]

    matched_names = [x.name for x in r0.matched_constraints]
    uncertain_names = [x.name for x in r0.uncertain_constraints]

    assert "kitchen" in matched_names
    assert "satellite TV" in uncertain_names
    assert "kitchen" not in uncertain_names

    assert len(r0.constraint_resolution_results) == 2
    assert r0.constraint_resolution_results[0].normalized_text == "kitchen"
    assert r0.constraint_resolution_results[1].normalized_text == "satellite TV"


def test_normalize_search_response_includes_selection_metadata():
    req = SearchRequest(
        city="Baku",
        check_in=date(2026, 4, 8),
        check_out=date(2026, 4, 15),
        constraints=[],
    )

    listing = ListingRaw(
        id="listing-1",
        name="Apartment STEL",
        url="https://example.com/stel",
        price=700.0,
        currency="US$",
        rooms=[],
    )

    ranked = [
        {
            "listing_name": "Apartment STEL",
            "listing": listing,
            "matches": {},
            "numeric_results": [],
            "property_result": None,
            "occupancy_result": None,
            "score": 23.0,
            "eligibility_status": "eligible",
            "match_tier": "strong",
            "selection_reasons": ["all required constraints are confirmed"],
            "blocking_reasons": [],
            "why": ["Good fit"],
        }
    ]

    out = normalize_search_response(
        req,
        ranked,
        top_n=5,
        dropped_requests=[],
    )

    assert len(out.results) == 1
    r0 = out.results[0]
    assert r0.eligibility_status == "eligible"
    assert r0.match_tier == "strong"
    assert r0.selection_reasons == ["all required constraints are confirmed"]
    assert r0.blocking_reasons == []