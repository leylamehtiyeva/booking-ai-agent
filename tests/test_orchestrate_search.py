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
        "check_in": "2026-04-08",
        "check_out": "2026-04-15",
        "must_have_fields": ["kitchen"],
        "nice_to_have_fields": [],
        "unknown_requests": [],
    }
    out = await orchestrate_search("Baku", intent, source="fixtures", max_items=10)
    assert out["need_clarification"] is False
    assert out["results"][0]["title"] == "Large Family Apartment"


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
        "property_types": ["apartment", "NOT_REAL_TYPE"],
        "occupancy_types": ["entire_place", "NOT_REAL_OCCUPANCY"],
        "filters": {
            "bedrooms_min": 2,
            "bedrooms_max": None,
            "area_sqm_min": 80,
            "area_sqm_max": None,
            "bathrooms_min": 2,
            "bathrooms_max": None,
            "price": {
                "min_amount": None,
                "max_amount": 50,
                "currency": "USD",
                "scope": "per_night",
            },
        },
        "unknown_requests": [],
    }

    out = _salvage_only_enum_keys(raw)

    assert out["filters"] == {
        "bedrooms_min": 2,
        "bedrooms_max": None,
        "area_sqm_min": 80,
        "area_sqm_max": None,
        "bathrooms_min": 2,
        "bathrooms_max": None,
        
        "price": {
            "min_amount": None,
            "max_amount": 50,
            "currency": "USD",
            "scope": "per_night",
        },
    }
    assert out["property_types"] == ["apartment"]
    assert out["occupancy_types"] == ["entire_place"]
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
    assert out["results"][0]["result_id"] == "big-1"
    assert any("BEDROOMS:" in x for x in out["results"][0]["why"])
    assert any("AREA:" in x for x in out["results"][0]["why"])
    
    
    
@pytest.mark.asyncio
async def test_price_filter_per_night_is_applied(monkeypatch):
    async def fake_get_candidates(req, max_items, source):
        return [
            ListingRaw(
                id="too-expensive",
                name="Apartment STEL",
                url="https://example.com/baku-expensive",
                description="Apartment in Baku city center.",
                price=700.0,
                currency="US$",
                available_dates={"check_in": "2026-04-01", "check_out": "2026-04-30"},
                rooms=[],
            ),
            ListingRaw(
                id="good-price",
                name="Budget Apartment",
                url="https://example.com/baku-budget",
                description="Budget apartment in Baku.",
                price=300.0,
                currency="US$",
                available_dates={"check_in": "2026-04-01", "check_out": "2026-04-30"},
                rooms=[],
            ),
        ]

    monkeypatch.setattr(orchestrate_search_tool, "get_candidates", fake_get_candidates)

    intent = {
        "city": "Baku",
        "check_in": "2026-04-08",
        "check_out": "2026-04-15",
        "must_have_fields": [],
        "nice_to_have_fields": [],
        "filters": {
            "price": {
                "max_amount": 50,
                "currency": "USD",
                "scope": "per_night",
            }
        },
        "unknown_requests": [],
    }

    out = await orchestrate_search_tool.orchestrate_search(
        "Apartment in Baku under 50 USD per night",
        intent,
        source="fixtures",
        max_items=10,
    )

    assert out["need_clarification"] is False
    assert len(out["results"]) == 1
    assert out["results"][0]["result_id"] == "good-price"
    assert any("PRICE:" in x for x in out["results"][0]["why"])
    
    
@pytest.mark.asyncio
async def test_bathroom_filter_is_applied(monkeypatch):
    async def fake_get_candidates(req, max_items, source):
        return [
            ListingRaw(
                id="one-bathroom",
                name="Apartment in Baku",
                url="https://example.com/baku-one-bathroom",
                description="Nice apartment in Baku with 1 bathroom.",
                rooms=[],
            ),
            ListingRaw(
                id="two-bathrooms",
                name="Family apartment in Baku",
                url="https://example.com/baku-two-bathrooms",
                description="Family apartment in Baku with 2 bathrooms.",
                rooms=[],
            ),
        ]

    monkeypatch.setattr(orchestrate_search_tool, "get_candidates", fake_get_candidates)

    intent = {
        "city": "Baku",
        "check_in": "2026-04-08",
        "check_out": "2026-04-15",
        "must_have_fields": [],
        "nice_to_have_fields": [],
        "filters": {
            "bathrooms_min": 2,
        },
        "unknown_requests": [],
    }

    out = await orchestrate_search_tool.orchestrate_search(
        "Apartment in Baku with at least 2 bathrooms",
        intent,
        source="fixtures",
        max_items=10,
    )

    assert out["need_clarification"] is False
    assert len(out["results"]) == 1
    assert out["results"][0]["result_id"]== "two-bathrooms"
    assert any("BATHROOMS:" in x for x in out["results"][0]["why"])
    
    
@pytest.mark.asyncio
async def test_property_type_filter_is_applied(monkeypatch):
    async def fake_get_candidates(req, max_items, source):
        return [
            ListingRaw(
                id="hotel-one",
                name="Hotel in Baku",
                url="https://example.com/baku-hotel",
                description="Nice hotel in Baku.",
                rooms=[],
            ),
            ListingRaw(
                id="apartment-one",
                name="Apartment in Baku",
                url="https://example.com/baku-apartment",
                description="Entire apartment in Baku with kitchen.",
                rooms=[],
            ),
        ]

    monkeypatch.setattr(orchestrate_search_tool, "get_candidates", fake_get_candidates)

    intent = {
        "city": "Baku",
        "check_in": "2026-04-08",
        "check_out": "2026-04-15",
        "must_have_fields": [],
        "nice_to_have_fields": [],
        "filters": {},
        "property_types": ["apartment"],
        "occupancy_types": [],
        "unknown_requests": [],
    }

    out = await orchestrate_search_tool.orchestrate_search(
        "Apartment in Baku",
        intent,
        source="fixtures",
        max_items=10,
    )

    assert out["need_clarification"] is False
    assert len(out["results"]) == 1
    assert out["results"][0]["result_id"] == "apartment-one"
    assert any("PROPERTY_TYPE:" in x for x in out["results"][0]["why"])
    
    
import pytest

from app.tools import orchestrate_search_tool
from app.schemas.listing import ListingRaw


@pytest.mark.asyncio
async def test_orchestrate_search_returns_normalized_response(monkeypatch):
    async def fake_get_candidates(req, max_items, source):
        return [
            ListingRaw(
                id=None,
                name="Apartment in Baku",
                url="https://example.com/baku-apartment",
                description="Apartment in Baku with private kitchen and private bathroom.",
                price=300.0,
                currency="US$",
                rooms=[],
                available_dates={"check_in": "2026-04-01", "check_out": "2026-04-30"},
            ),
        ]

    monkeypatch.setattr(orchestrate_search_tool, "get_candidates", fake_get_candidates)

    intent = {
        "city": "Baku",
        "check_in": "2026-04-08",
        "check_out": "2026-04-15",
        "must_have_fields": ["kitchen"],
        "nice_to_have_fields": [],
        "filters": {},
        "property_types": ["apartment"],
        "occupancy_types": [],
        "unknown_requests": [],
    }

    out = await orchestrate_search_tool.orchestrate_search(
        "Apartment in Baku with kitchen",
        intent,
        source="fixtures",
        max_items=10,
        fallback_top_k=0,
    )

    assert out["need_clarification"] is False
    assert "request_summary" in out
    assert "results" in out

    assert out["request_summary"]["city"] == "Baku"
    assert out["request_summary"]["must_have_fields"] == ["kitchen"]
    assert out["request_summary"]["property_types"] == ["apartment"]

    assert len(out["results"]) == 1
    first = out["results"][0]

    assert "result_id" in first
    assert first["title"] == "Apartment in Baku"
    assert first["url"] == "https://example.com/baku-apartment"
    assert "matched_constraints" in first
    assert "uncertain_constraints" in first
    assert "facts" in first
    
    import pytest


@pytest.mark.asyncio
async def test_orchestrate_search_attaches_unknown_request_results():
    intent = {
        "city": "Baku",
        "check_in": "2026-04-08",
        "check_out": "2026-04-15",
        "must_have_fields": ["iron"],
        "nice_to_have_fields": [],
        "unknown_requests": ["satellite TV"],
        "property_types": ["apartment"],
        "occupancy_types": [],
        "filters": {},
    }

    out = await orchestrate_search(
        "I want an apartment in Baku with satellite TV and ironing facilities",
        intent,
        source="fixtures",
        max_items=5,
    )

    assert out["need_clarification"] is False
    assert out["results"]

    first = out["results"][0]
    assert "unknown_request_results" in first
    assert isinstance(first["unknown_request_results"], list)

    unknowns = first["unknown_request_results"]
    assert unknowns
    assert unknowns[0]["query_text"] == "satellite TV"
    assert unknowns[0]["value"] in {"FOUND", "NOT_FOUND", "UNCERTAIN"}
    assert "reason" in unknowns[0]
    
    
@pytest.mark.asyncio
async def test_orchestrate_search_attaches_unknown_request_results():
    intent = {
        "city": "Baku",
        "check_in": "2026-04-08",
        "check_out": "2026-04-15",
        "must_have_fields": ["iron"],
        "nice_to_have_fields": [],
        "unknown_requests": ["satellite TV"],
        "property_types": ["apartment"],
        "occupancy_types": [],
        "filters": {},
    }

    out = await orchestrate_search(
        "I want an apartment in Baku with satellite TV and ironing facilities",
        intent,
        source="fixtures",
        max_items=5,
    )

    assert out["need_clarification"] is False
    assert out["results"]

    found_unknown = False
    for result in out["results"]:
        assert "unknown_request_results" in result
        assert isinstance(result["unknown_request_results"], list)

        for item in result["unknown_request_results"]:
            if item["query_text"] == "satellite TV":
                found_unknown = True
                assert item["value"] in {"FOUND", "UNCERTAIN", "NOT_FOUND"}
                assert "reason" in item

    assert found_unknown