from app.logic.occupancy import extract_listing_max_occupancy, evaluate_occupancy
from app.schemas.query import SearchRequest


class Opt:
    def __init__(self, persons):
        self.persons = persons


class Room:
    def __init__(self, persons=None, options=None, available=True):
        self.persons = persons
        self.options = options or []
        self.available = available


class Listing:
    def __init__(self, rooms):
        self.rooms = rooms


def test_extract_listing_max_occupancy_prefers_option_persons():
    listing = Listing(
        rooms=[
            Room(persons=2, options=[Opt(8)], available=True),
        ]
    )

    cap = extract_listing_max_occupancy(listing)
    assert cap == 8


def test_extract_listing_max_occupancy_falls_back_to_room_persons():
    listing = Listing(
        rooms=[
            Room(persons=4, options=[], available=True),
        ]
    )

    cap = extract_listing_max_occupancy(listing)
    assert cap == 4


def test_evaluate_occupancy_passes_when_capacity_is_enough():
    listing = Listing(
        rooms=[
            Room(persons=2, options=[Opt(8)], available=True),
        ]
    )

    req = SearchRequest(
        user_message="test",
        city="Baku",
        adults=4,
        children=2,
        rooms=1,
    )

    result = evaluate_occupancy(listing, req)
    assert result.passed is True
    assert result.listing_capacity == 8


def test_evaluate_occupancy_fails_when_capacity_is_too_small():
    listing = Listing(
        rooms=[
            Room(persons=2, options=[Opt(4)], available=True),
        ]
    )

    req = SearchRequest(
        user_message="test",
        city="Baku",
        adults=5,
        children=1,
        rooms=1,
    )

    result = evaluate_occupancy(listing, req)
    assert result.passed is False
    assert result.listing_capacity == 4


def test_evaluate_occupancy_keeps_listing_when_capacity_unknown():
    listing = Listing(rooms=[])

    req = SearchRequest(
        user_message="test",
        city="Baku",
        adults=3,
        children=0,
        rooms=1,
    )

    result = evaluate_occupancy(listing, req)
    assert result.passed is True
    assert result.listing_capacity is None