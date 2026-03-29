from app.logic.listing_signals import collect_listing_signals
from app.schemas.listing import ListingRaw, Room, RoomOption


def test_collect_listing_signals_from_listing_and_rooms():
    listing = ListingRaw(
        id="x1",
        name="CHINAR Apartment",
        property_type="apartment",
        description="Spacious apartment in Baku center",
        facilities=[{"name": "Free WiFi"}, {"name": "Air conditioning"}],
        rooms=[
            Room(
                name="Three-Bedroom Apartment",
                facilities=["Private kitchen", "Private bathroom"],
                options=[
                    RoomOption(
                        name="Deluxe rate",
                        yourChoices=["Free cancellation", "No prepayment needed"],
                    )
                ],
                roomType="Three-Bedroom Apartment with View",
                bedTypes=["3 single beds", "1 sofa bed"],
            )
        ],
    )

    signals = collect_listing_signals(listing)

    texts = [s.text for s in signals]
    paths = [s.path for s in signals]

    assert "chinar apartment" in texts
    assert "apartment" in texts
    assert "spacious apartment in baku center" in texts
    assert "free wifi" in texts
    assert "air conditioning" in texts
    assert "three-bedroom apartment" in texts
    assert "three-bedroom apartment with view" in texts
    assert "private kitchen" in texts
    assert "private bathroom" in texts
    assert "deluxe rate" in texts
    assert "free cancellation" in texts
    assert "no prepayment needed" in texts
    assert "3 single beds" in texts

    assert "listing.name" in paths
    assert "listing.property_type" in paths
    assert "listing.description" in paths
    assert "listing.facilities" in paths
    assert "rooms[0].name" in paths
    assert "rooms[0].roomType" in paths
    assert "rooms[0].facilities" in paths
    assert "rooms[0].options[0].name" in paths
    assert "rooms[0].options[0].yourChoices" in paths
    assert "rooms[0].bedTypes" in paths


def test_collect_listing_signals_from_highlights_and_policies():
    listing = ListingRaw(
        id="x2",
        name="Nice stay",
        highlights=[
            {"title": "Great for your stay", "contents": ["Balcony", "City view"]},
        ],
        policies=[
            {"title": "Pets", "content": "Pets are allowed on request."},
            {"title": "Smoking", "content": "Non-smoking throughout."},
        ],
    )

    signals = collect_listing_signals(listing)
    texts = [s.text for s in signals]

    assert "great for your stay" in texts
    assert "balcony" in texts
    assert "city view" in texts
    assert "pets" in texts
    assert "pets are allowed on request." in texts
    assert "smoking" in texts
    assert "non-smoking throughout." in texts