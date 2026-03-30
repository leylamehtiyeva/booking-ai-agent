from app.logic.result_ids import build_result_id
from app.schemas.listing import ListingRaw


def test_build_result_id_uses_listing_id():
    listing = ListingRaw(
        id="abc123",
        name="Apartment One",
        rooms=[],
    )

    rid = build_result_id(listing)

    assert rid == "abc123"


def test_build_result_id_falls_back_to_url():
    listing = ListingRaw(
        id=None,
        name="Apartment One",
        url="https://example.com/a1",
        rooms=[],
    )

    rid = build_result_id(listing)

    assert rid.startswith("url_")
    assert len(rid) > 4


def test_build_result_id_falls_back_to_generated_hash():
    listing = ListingRaw(
        id=None,
        name="Apartment One",
        description="Nice apartment in city center",
        rooms=[],
    )

    rid = build_result_id(listing)

    assert rid.startswith("gen_")
    assert len(rid) > 4