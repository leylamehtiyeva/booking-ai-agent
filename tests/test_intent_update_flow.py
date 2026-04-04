from datetime import date

import pytest

from app.logic.intent_update import update_search_state_async
from app.schemas.fields import Field
from app.schemas.filters import SearchFilters
from app.schemas.intent_patch import SearchIntentPatch
from app.schemas.query import SearchRequest


@pytest.mark.asyncio
async def test_update_search_state_adds_field_and_updates_filter(monkeypatch):
    async def _fake_patch(previous_state, user_message):
        return SearchIntentPatch(
            add_must_have_fields=[Field.KETTLE],
            set_filters=SearchFilters(bedrooms_min=3),
        )

    monkeypatch.setattr(
        "app.logic.intent_update.route_intent_update_patch_async",
        _fake_patch,
    )

    previous_state = SearchRequest(
        user_message="initial",
        city="Baku",
        check_in=date(2026, 4, 20),
        check_out=date(2026, 4, 26),
        must_have_fields=[Field.KITCHEN],
        filters=SearchFilters(area_sqm_min=80, bedrooms_min=2),
    )

    updated = await update_search_state_async(
        previous_state,
        "Also I want a kettle, and now at least 3 bedrooms.",
    )

    assert updated.city == "Baku"
    assert updated.check_in == date(2026, 4, 20)
    assert updated.check_out == date(2026, 4, 26)
    assert Field.KITCHEN in updated.must_have_fields
    assert Field.KETTLE in updated.must_have_fields
    assert updated.filters.bedrooms_min == 3
    assert updated.filters.area_sqm_min == 80