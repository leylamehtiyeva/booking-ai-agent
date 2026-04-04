from datetime import date

import pytest

from app.schemas.fields import Field
from app.schemas.filters import SearchFilters
from app.schemas.query import SearchRequest


@pytest.mark.asyncio
async def test_conversation_flow_first_turn_builds_state_and_searches(monkeypatch):
    async def _fake_build_search_request(user_message: str) -> SearchRequest:
        return SearchRequest(
            user_message=user_message,
            city="Baku",
            check_in=date(2026, 4, 20),
            check_out=date(2026, 4, 26),
            must_have_fields=[Field.KITCHEN],
        )

    async def _fake_orchestrate_search(**kwargs):
        return {
            "need_clarification": False,
            "results": [{"title": "Large Family Apartment"}],
        }

    monkeypatch.setattr(
        "app.logic.conversation_flow.build_search_request_adk_async",
        _fake_build_search_request,
    )
    monkeypatch.setattr(
        "app.logic.conversation_flow.orchestrate_search",
        _fake_orchestrate_search,
    )

    from app.logic.conversation_flow import handle_user_message

    out = await handle_user_message(
        "I want an apartment in Baku from 2026-04-20 for 6 nights with kitchen"
    )

    assert out["need_clarification"] is False
    assert out["results"][0]["title"] == "Large Family Apartment"
    assert out["state"]["city"] == "Baku"
    assert out["state"]["must_have_fields"] == ["kitchen"]


@pytest.mark.asyncio
async def test_conversation_flow_followup_updates_existing_state(monkeypatch):
    previous_state = SearchRequest(
        user_message="initial",
        city="Baku",
        check_in=date(2026, 4, 20),
        check_out=date(2026, 4, 26),
        must_have_fields=[Field.KITCHEN],
        filters=SearchFilters(bedrooms_min=2),
    )

    async def _fake_update_search_state(prev_state: SearchRequest, user_message: str) -> SearchRequest:
        return SearchRequest(
            user_message=prev_state.user_message,
            city=prev_state.city,
            check_in=prev_state.check_in,
            check_out=prev_state.check_out,
            must_have_fields=[Field.KITCHEN, Field.KETTLE],
            filters=SearchFilters(bedrooms_min=3),
        )

    async def _fake_orchestrate_search(**kwargs):
        return {
            "need_clarification": False,
            "results": [{"title": "Large Family Apartment"}],
        }

    monkeypatch.setattr(
        "app.logic.conversation_flow.update_search_state_async",
        _fake_update_search_state,
    )
    monkeypatch.setattr(
        "app.logic.conversation_flow.orchestrate_search",
        _fake_orchestrate_search,
    )

    from app.logic.conversation_flow import handle_user_message

    out = await handle_user_message(
        "Also I want a kettle, and now at least 3 bedrooms.",
        previous_state=previous_state,
    )

    assert out["need_clarification"] is False
    assert out["state"]["city"] == "Baku"
    assert sorted(out["state"]["must_have_fields"]) == ["kettle", "kitchen"]
    assert out["state"]["filters"]["bedrooms_min"] == 3


@pytest.mark.asyncio
async def test_conversation_flow_returns_clarification_if_updated_state_is_incomplete(monkeypatch):
    previous_state = SearchRequest(
        user_message="initial",
        city="Baku",
        check_in=date(2026, 4, 20),
        check_out=date(2026, 4, 26),
        must_have_fields=[Field.KITCHEN],
    )

    async def _fake_update_search_state(prev_state: SearchRequest, user_message: str) -> SearchRequest:
        return SearchRequest(
            user_message=prev_state.user_message,
            city=None,
            check_in=prev_state.check_in,
            check_out=prev_state.check_out,
            must_have_fields=prev_state.must_have_fields,
        )

    monkeypatch.setattr(
        "app.logic.conversation_flow.update_search_state_async",
        _fake_update_search_state,
    )

    from app.logic.conversation_flow import handle_user_message

    out = await handle_user_message(
        "City does not matter anymore.",
        previous_state=previous_state,
    )

    assert out["need_clarification"] is True
    assert any("city" in q.lower() for q in out["questions"])
    assert out["state"]["check_in"] == "2026-04-20"
    assert out["state"]["check_out"] == "2026-04-26"
    