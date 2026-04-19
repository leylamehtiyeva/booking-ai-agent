from app.logic.matcher_structured import match_listing_structured
from app.schemas.fields import Field
from app.schemas.listing import ListingRaw
from app.schemas.match import Ternary
from app.schemas.query import SearchRequest
from app.schemas.constraints import (
    UserConstraint,
    ConstraintPriority,
    ConstraintCategory,
    ConstraintMappingStatus,
    EvidenceStrategy,
)

def test_pet_friendly_negative_rule_returns_no():
    listing = ListingRaw(
        id="x1",
        name="Hotel Example",
        policies=[
            {"title": "Pets", "content": "Pets are not allowed."},
        ],
    )

    req = SearchRequest(
        city="Baku",
        check_in="2026-04-08",
        check_out="2026-04-15",
        adults=2,
        children=0,
        rooms=1,
        currency="USD",
        constraints=[
    UserConstraint(
        raw_text="pet friendly",
        normalized_text="pet friendly",
        priority=ConstraintPriority.MUST,
        category=ConstraintCategory.POLICY,
        mapping_status=ConstraintMappingStatus.KNOWN,
        mapped_fields=[Field.PET_FRIENDLY],
        evidence_strategy=EvidenceStrategy.STRUCTURED,
    )
]
    )

    report = match_listing_structured(listing, req)

    assert report.matches[Field.PET_FRIENDLY].value == Ternary.NO
    assert report.matches[Field.PET_FRIENDLY].evidence
    assert "Pets are not allowed." in report.matches[Field.PET_FRIENDLY].evidence[0].snippet


def test_free_cancellation_negative_rule_returns_no():
    listing = ListingRaw(
        id="x2",
        name="Stay",
        policies=[
            {"title": "Cancellation", "content": "This booking is non-refundable."},
        ],
    )

    req = SearchRequest(
    city="Baku",
    check_in="2026-04-08",
    check_out="2026-04-15",
    adults=2,
    children=0,
    rooms=1,
    currency="USD",
    constraints=[
        UserConstraint(
            raw_text="free cancellation",
            normalized_text="free cancellation",
            priority=ConstraintPriority.MUST,
            category=ConstraintCategory.POLICY,
            mapping_status=ConstraintMappingStatus.KNOWN,
            mapped_fields=[Field.FREE_CANCELLATION],
            evidence_strategy=EvidenceStrategy.STRUCTURED,
        )
    ],
)

    report = match_listing_structured(listing, req)

    assert report.matches[Field.FREE_CANCELLATION].value == Ternary.NO
    assert report.matches[Field.FREE_CANCELLATION].evidence
    assert "non-refundable" in report.matches[Field.FREE_CANCELLATION].evidence[0].snippet.lower()


def test_private_bathroom_negative_rule_shared_bathroom_returns_no():
    listing = ListingRaw(
        id="x3",
        name="Budget room",
        description="Room with shared bathroom in city center",
    )

    req = SearchRequest(
    city="Baku",
    check_in="2026-04-08",
    check_out="2026-04-15",
    adults=2,
    children=0,
    rooms=1,
    currency="USD",
    constraints=[
        UserConstraint(
            raw_text="private bathroom",
            normalized_text="private bathroom",
            priority=ConstraintPriority.MUST,
            category=ConstraintCategory.AMENITY,
            mapping_status=ConstraintMappingStatus.KNOWN,
            mapped_fields=[Field.PRIVATE_BATHROOM],
            evidence_strategy=EvidenceStrategy.STRUCTURED,
        )
    ],
)

    report = match_listing_structured(listing, req)

    assert report.matches[Field.PRIVATE_BATHROOM].value == Ternary.NO