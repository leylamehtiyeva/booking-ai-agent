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
