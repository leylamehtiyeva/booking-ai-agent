import pytest

from app.tools.orchestrate_search_tool import orchestrate_search


@pytest.mark.asyncio
async def test_orchestrate_search_returns_constraint_statuses():
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

    assert "constraint_statuses" in out
    assert isinstance(out["constraint_statuses"], list)
    assert out["constraint_statuses"]

    first = out["constraint_statuses"][0]
    assert "constraint" in first
    assert first["constraint"]["normalized_text"] == "satellite TV"
    assert first["value"] in {"FOUND", "NOT_FOUND", "UNCERTAIN"}
    assert "reason" in first