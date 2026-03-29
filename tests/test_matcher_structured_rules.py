from app.logic.matcher_structured import match_listing_structured
from app.schemas.fields import Field
from app.schemas.listing import ListingRaw, Room, RoomOption
from app.schemas.match import Ternary
from app.schemas.query import SearchRequest


def test_match_listing_structured_uses_signal_rules():
    listing = ListingRaw(
        id="x1",
        name="CHINAR Apartment DeLux",
        property_type="apartment",
        description="Spacious stay in Baku center",
        facilities=[{"name": "Free WiFi"}],
        rooms=[
            Room(
                name="Three-Bedroom Apartment",
                roomType="Three-Bedroom Apartment with Balcony",
                facilities=["Private kitchen", "Private bathroom", "Washing machine"],
                options=[
                    RoomOption(
                        name="Flexible rate",
                        yourChoices=["Free cancellation", "No prepayment needed"],
                    )
                ],
            )
        ],
        policies=[
            {"title": "Pets", "content": "Pets are allowed on request."},
        ],
    )

    req = SearchRequest(
        user_message="test",
        city="Baku",
        check_in="2026-04-08",
        check_out="2026-04-15",
        adults=2,
        children=0,
        rooms=1,
        currency="USD",
        must_have_fields=[
            Field.PRIVATE_BATHROOM,
            Field.KITCHEN,
            Field.PROPERTY_APARTMENT,
        ],
        nice_to_have_fields=[
            Field.WIFI,
            Field.WASHING_MACHINE,
            Field.FREE_CANCELLATION,
            Field.PET_FRIENDLY,
            Field.BALCONY,
        ],
    )

    report = match_listing_structured(listing, req)

    assert report.matches[Field.PRIVATE_BATHROOM].value == Ternary.YES
    assert report.matches[Field.KITCHEN].value == Ternary.YES
    assert report.matches[Field.PROPERTY_APARTMENT].value == Ternary.YES

    assert report.matches[Field.WIFI].value == Ternary.YES
    assert report.matches[Field.WASHING_MACHINE].value == Ternary.YES
    assert report.matches[Field.FREE_CANCELLATION].value == Ternary.YES
    assert report.matches[Field.PET_FRIENDLY].value == Ternary.YES
    assert report.matches[Field.BALCONY].value == Ternary.YES
    