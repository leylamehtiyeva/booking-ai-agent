import pytest
from datetime import date

from app.agents.intent_router_agent import IntentRoute
from app.logic.request_resolution import resolve_required_search_context
from app.tools.orchestrate_search_tool import orchestrate_search
from app.schemas.fallback_policy import FallbackPolicy


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

    out, dropped_requests = _salvage_only_enum_keys(raw)

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

    # A3 contract:
    # invalid legacy residue is reported separately, not pushed into unknown_requests.
    assert out["unknown_requests"] == []
    assert "NOT_A_REAL_FIELD" in dropped_requests
    assert "NOT_REAL_TYPE" in dropped_requests
    assert "NOT_REAL_OCCUPANCY" in dropped_requests
    
    
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
        fallback_policy=FallbackPolicy(enabled=True, top_k=0),
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
    assert "constraints" in out["request_summary"]
    assert out["request_summary"]["constraints"]
    assert out["request_summary"]["constraints"][0]["normalized_text"] == "kitchen"
    
    import pytest



    

@pytest.mark.asyncio
async def test_constraint_resolution_results_are_attached_and_can_influence_ranking():
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
        fallback_policy=FallbackPolicy(enabled=True),

    )

    assert out["need_clarification"] is False
    assert out["results"]

    titles = [r["title"] for r in out["results"]]
    assert "Compact Apartment" in titles

    compact = next(r for r in out["results"] if r["title"] == "Compact Apartment")

    assert "constraint_resolution_results" in compact
    assert isinstance(compact["constraint_resolution_results"], list)
    assert compact["constraint_resolution_results"]

    satellite_items = [
        item
        for item in compact["constraint_resolution_results"]
        if item["normalized_text"] == "satellite TV"
    ]
    assert satellite_items

    satellite = satellite_items[0]
    assert satellite["decision"] in {"YES", "NO", "UNCERTAIN"}
    assert satellite["resolution_status"] in {"matched", "failed", "uncertain"}
    assert "reason" in satellite

    # ranking/explainability signal from fallback should be visible in why
    assert any(
        "satellite tv" in reason.lower()
        for reason in compact.get("why", [])
    )
    
    
@pytest.mark.asyncio
async def test_unknown_request_found_improves_listing_priority():
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
        fallback_policy=FallbackPolicy(enabled=True),

    )

    assert out["need_clarification"] is False
    assert out["results"]

    # Soft check: found listing should be near the top
    top_titles = [r["title"] for r in out["results"][:2]]
    assert "Compact Apartment" in top_titles
    
    
def test_resolve_required_search_context_missing_city_and_dates():
    intent = IntentRoute(
        city=None,
        check_in=None,
        check_out=None,
        nights=None,
        must_have_fields=[],
        nice_to_have_fields=[],
        unknown_requests=[],
    )

    resolved = resolve_required_search_context(intent)

    assert resolved.need_clarification is True
    assert any("city" in q.lower() for q in resolved.questions)
    assert any("date" in q.lower() or "travel dates" in q.lower() for q in resolved.questions)
    
    
def test_resolve_required_search_context_single_date_defaults_to_one_night():
    intent = IntentRoute(
        city="Baku",
        check_in="2026-04-20",
        check_out=None,
        nights=1,
        must_have_fields=[],
        nice_to_have_fields=[],
        unknown_requests=[],
    )

    resolved = resolve_required_search_context(intent)

    assert resolved.need_clarification is False
    assert resolved.check_in == date(2026, 4, 20)
    assert resolved.check_out == date(2026, 4, 21)
    
    
def test_resolve_required_search_context_from_date_for_n_nights():
    intent = IntentRoute(
        city="Baku",
        check_in="2026-04-20",
        check_out=None,
        nights=6,
        must_have_fields=[],
        nice_to_have_fields=[],
        unknown_requests=[],
    )

    resolved = resolve_required_search_context(intent)

    assert resolved.need_clarification is False
    assert resolved.check_in == date(2026, 4, 20)
    assert resolved.check_out == date(2026, 4, 26)
    
    
@pytest.mark.asyncio
async def test_missing_city_requires_clarification():
    intent = {
        "city": None,
        "check_in": "2026-04-08",
        "check_out": "2026-04-15",
        "must_have_fields": [],
        "nice_to_have_fields": [],
        "unknown_requests": [],
    }

    out = await orchestrate_search("Need a place from 2026-04-08 to 2026-04-15", intent, source="fixtures", max_items=10)

    assert out["need_clarification"] is True
    assert any("city" in q.lower() for q in out["questions"])
    
    
    
@pytest.mark.asyncio
async def test_single_date_without_checkout_searches_one_night():
    intent = {
        "city": "Baku",
        "check_in": "2026-04-08",
        "check_out": None,
        "nights": 1,
        "must_have_fields": ["kitchen"],
        "nice_to_have_fields": [],
        "unknown_requests": [],
    }

    out = await orchestrate_search("Baku on 2026-04-08 with kitchen", intent, source="fixtures", max_items=10)

    assert out["need_clarification"] is False
    assert out["results"][0]["title"] == "Large Family Apartment"
    
    
@pytest.mark.asyncio
async def test_from_date_for_n_nights_is_resolved_before_search():
    intent = {
        "city": "Baku",
        "check_in": "2026-04-08",
        "check_out": None,
        "nights": 7,
        "must_have_fields": ["kitchen"],
        "nice_to_have_fields": [],
        "unknown_requests": [],
    }

    out = await orchestrate_search("Baku from 2026-04-08 for 7 nights with kitchen", intent, source="fixtures", max_items=10)

    assert out["need_clarification"] is False
    assert out["results"][0]["title"] == "Large Family Apartment"
    
    
@pytest.mark.asyncio
async def test_occupancy_filter_is_applied():
    intent = {
        "city": "Baku",
        "check_in": "2026-04-08",
        "check_out": "2026-04-15",
        "adults": 7,
        "children": 0,
        "rooms": 1,
        "must_have_fields": ["kitchen"],
        "nice_to_have_fields": [],
        "unknown_requests": [],
    }

    out = await orchestrate_search(
        "Apartment in Baku for 7 adults with kitchen",
        intent,
        source="fixtures",
        max_items=10,
        fallback_policy=FallbackPolicy(enabled=True),

    )

    assert out["need_clarification"] is False