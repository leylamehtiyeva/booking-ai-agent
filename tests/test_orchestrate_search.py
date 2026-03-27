import pytest

from app.tools.orchestrate_search_tool import orchestrate_search


@pytest.mark.asyncio
async def test_no_dates_requires_clarification():
    intent = {
        "city": "Baku",
        "check_in": None,
        "check_out": None,
        "must_have_fields": [],
        "nice_to_have_fields": [],
        "unknown_requests": [],
    }
    out = await orchestrate_search("Baku", intent, source="fixtures", max_items=10)
    assert out["need_clarification"] is True


@pytest.mark.asyncio
async def test_baku_kitchen_returns_apartment():
    intent = {
        "city": "Baku",
        "check_in": "2026-02-12",
        "check_out": "2026-02-14",
        "must_have_fields": ["kitchen"],
        "nice_to_have_fields": [],
        "unknown_requests": [],
    }
    out = await orchestrate_search("Baku", intent, source="fixtures", max_items=10)
    assert out["need_clarification"] is False
    assert out["results"][0]["title"] == "Apartment with Kitchen and Kettle"


@pytest.mark.asyncio
async def test_tokyo_returns_no_results_on_fixtures():
    intent = {
        "city": "Tokyo",
        "check_in": "2026-02-12",
        "check_out": "2026-02-14",
        "must_have_fields": [],
        "nice_to_have_fields": [],
        "unknown_requests": [],
    }
    out = await orchestrate_search("Tokyo", intent, source="fixtures", max_items=10)
    assert out["need_clarification"] is True


from app.tools.orchestrate_search_tool import _salvage_only_enum_keys


def test_salvage_preserves_filters():
    raw = {
        "city": "Baku",
        "check_in": "2026-04-08",
        "check_out": "2026-04-15",
        "must_have_fields": ["kitchen", "NOT_A_REAL_FIELD"],
        "nice_to_have_fields": ["private_bathroom"],
        "filters": {
            "bedrooms_min": 2,
            "bedrooms_max": None,
            "area_sqm_min": 80,
            "area_sqm_max": None,
        },
        "unknown_requests": [],
    }

    out = _salvage_only_enum_keys(raw)

    assert out["filters"] == {
        "bedrooms_min": 2,
        "bedrooms_max": None,
        "area_sqm_min": 80,
        "area_sqm_max": None,
    }
    assert "NOT_A_REAL_FIELD" in out["unknown_requests"]
    
    
from app.schemas.listing import ListingRaw, Room
from app.tools import orchestrate_search_tool


@pytest.mark.asyncio
async def test_numeric_filters_are_applied_in_orchestrate(monkeypatch):
    async def fake_get_candidates(req, max_items, source):
        return [
            ListingRaw(
                id="small-1",
                name="One-Bedroom Apartment",
                url="https://example.com/small-1",
                description="Apartment in Baku, 45 sqm, private bathroom, kitchen.",
                available_dates={"check_in": "2026-02-01", "check_out": "2026-03-31"},
                facilities=[{"name": "Kitchen"}, {"name": "Private bathroom"}],
                rooms=[
                    Room(
                        name="One-Bedroom Apartment",
                        facilities=["Kitchen", "Private bathroom"],
                    )
                ],
            ),
            ListingRaw(
                id="big-1",
                name="Three-Bedroom Apartment",
                url="https://example.com/big-1",
                description="Apartment in Baku, 2196 feet², private bathroom, kitchen.",
                available_dates={"check_in": "2026-02-01", "check_out": "2026-03-31"},
                facilities=[{"name": "Kitchen"}, {"name": "Private bathroom"}],
                rooms=[
                    Room(
                        name="Three-Bedroom Apartment with Balcony",
                        facilities=["Kitchen", "Private bathroom"],
                    )
                ],
            ),
        ]

    monkeypatch.setattr(orchestrate_search_tool, "get_candidates", fake_get_candidates)

    intent = {
        "city": "Baku",
        "check_in": "2026-02-12",
        "check_out": "2026-02-14",
        "must_have_fields": ["kitchen", "private_bathroom"],
        "nice_to_have_fields": [],
        "filters": {
            "bedrooms_min": 2,
            "bedrooms_max": None,
            "area_sqm_min": 80,
            "area_sqm_max": None,
        },
        "unknown_requests": [],
    }

    out = await orchestrate_search_tool.orchestrate_search(
        "Apartment in Baku with private bathroom, kitchen, at least 2 bedrooms and at least 80 sqm",
        intent,
        source="fixtures",
        max_items=10,
    )

    assert out["need_clarification"] is False
    assert len(out["results"]) == 1
    assert out["results"][0]["id"] == "big-1"
    assert any("BEDROOMS:" in x for x in out["results"][0]["why"])
    assert any("AREA:" in x for x in out["results"][0]["why"])