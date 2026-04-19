import pytest

from app.tools.orchestrate_search_tool import orchestrate_search


@pytest.mark.asyncio
async def test_orchestrate_search_returns_constraint_statuses():
    intent = {
    "city": "Baku",
    "check_in": "2026-04-08",
    "check_out": "2026-04-15",
    "constraints": [
        {
            "raw_text": "ironing facilities",
            "normalized_text": "iron",
            "priority": "must",
            "category": "amenity",
            "mapping_status": "known",
            "mapped_fields": ["iron"],
            "evidence_strategy": "structured",
        },
        {
            "raw_text": "satellite TV",
            "normalized_text": "satellite TV",
            "priority": "must",
            "category": "amenity",
            "mapping_status": "unresolved",
            "mapped_fields": [],
            "evidence_strategy": "textual",
        },
    ],
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

    assert "normalized_text" in first
    assert "decision" in first
    assert "resolution_status" in first
    assert "reason" in first

    assert first["decision"] in {"YES", "NO", "UNCERTAIN"}
    assert first["resolution_status"] in {"matched", "failed", "uncertain"}

    assert any(
        item["normalized_text"] == "satellite TV"
        for item in out["constraint_statuses"]
    )