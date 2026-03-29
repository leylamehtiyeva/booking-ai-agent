from app.logic.matcher_structured import match_listing_structured
from app.schemas.fields import Field
from app.schemas.listing import ListingRaw
from app.schemas.match import Ternary
from app.schemas.query import SearchRequest


def test_pet_friendly_negative_rule_returns_no():
    listing = ListingRaw(
        id="x1",
        name="Hotel Example",
        policies=[
            {"title": "Pets", "content": "Pets are not allowed."},
        ],
    )

    req = SearchRequest(
        user_message="pet friendly place",
        city="Baku",
        check_in="2026-04-08",
        check_out="2026-04-15",
        adults=2,
        children=0,
        rooms=1,
        currency="USD",
        must_have_fields=[Field.PET_FRIENDLY],
        nice_to_have_fields=[],
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
        user_message="free cancellation",
        city="Baku",
        check_in="2026-04-08",
        check_out="2026-04-15",
        adults=2,
        children=0,
        rooms=1,
        currency="USD",
        must_have_fields=[Field.FREE_CANCELLATION],
        nice_to_have_fields=[],
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
        user_message="private bathroom",
        city="Baku",
        check_in="2026-04-08",
        check_out="2026-04-15",
        adults=2,
        children=0,
        rooms=1,
        currency="USD",
        must_have_fields=[Field.PRIVATE_BATHROOM],
        nice_to_have_fields=[],
    )

    report = match_listing_structured(listing, req)

    assert report.matches[Field.PRIVATE_BATHROOM].value == Ternary.NO