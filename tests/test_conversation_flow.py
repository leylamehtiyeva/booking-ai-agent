from datetime import date

import pytest

from app.schemas.fields import Field
from app.schemas.filters import SearchFilters
from app.schemas.query import SearchRequest


@pytest.mark.asyncio
async def test_conversation_flow_first_turn_builds_state_and_searches(monkeypatch):
    async def _fake_build_search_request(user_message: str) -> SearchRequest:
        return SearchRequest(
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



from app.schemas.fields import Field
from app.schemas.filters import SearchFilters
from app.schemas.query import SearchRequest
from app.schemas.conversation_route import ConversationRouteDecision


@pytest.mark.asyncio
async def test_conversation_flow_followup_updates_existing_state(monkeypatch):
    previous_state = SearchRequest(
        city="Baku",
        check_in=date(2026, 4, 20),
        check_out=date(2026, 4, 26),
        must_have_fields=[Field.KITCHEN],
        filters=SearchFilters(bedrooms_min=2),
    )

    async def _fake_route_conversation_async(**kwargs) -> ConversationRouteDecision:
        return ConversationRouteDecision(
            route="search_update",
            reason="user updates current search",
        )

    async def _fake_update_search_state(prev_state: SearchRequest, user_message: str) -> SearchRequest:
        return SearchRequest(
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
        "app.logic.conversation_flow.route_conversation_async",
        _fake_route_conversation_async,
    )
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
    assert out["state"]["must_have_fields"] == ["kitchen", "kettle"]
    assert out["state"]["filters"]["bedrooms_min"] == 3
    assert out["results"][0]["title"] == "Large Family Apartment"


@pytest.mark.asyncio
async def test_conversation_flow_returns_clarification_if_updated_state_is_incomplete(monkeypatch):
    previous_state = SearchRequest(
        city="Baku",
        check_in=date(2026, 4, 20),
        check_out=date(2026, 4, 26),
        must_have_fields=[Field.KITCHEN],
    )

    async def _fake_update_search_state(prev_state: SearchRequest, user_message: str) -> SearchRequest:
        return SearchRequest(
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
    
    
@pytest.mark.asyncio
async def test_conversation_flow_listing_question_does_not_mutate_state(monkeypatch):
    previous_state = SearchRequest(
        city="Baku",
        must_have_fields=[],
        unknown_requests=["2 beds"],
    )

    async def _fake_route_conversation(**kwargs):
        from app.schemas.conversation_route import ConversationRouteDecision
        return ConversationRouteDecision(
            route="listing_question",
            reason="Question about shown listing",
        )

    async def _fake_answer_listing_question(**kwargs):
        return {
            "need_clarification": False,
            "response_type": "listing_question",
            "answer": "1 bed option is explicitly mentioned in the listing.",
            "state": previous_state.model_dump(mode="json", exclude_none=True),
        }

    monkeypatch.setattr(
        "app.logic.conversation_flow.route_conversation_async",
        _fake_route_conversation,
    )
    monkeypatch.setattr(
        "app.logic.conversation_flow._answer_listing_question",
        _fake_answer_listing_question,
    )

    from app.logic.conversation_flow import handle_user_message

    out = await handle_user_message(
        "Есть ли у этого отеля вариант с 1 кроватью?",
        previous_state=previous_state,
        shown_listing={"name": "Test Hotel"},
    )

    assert out["response_type"] == "listing_question"
    assert out["state"]["unknown_requests"] == ["2 beds"]
    
    
@pytest.mark.asyncio
async def test_conversation_flow_returns_clarification_if_updated_state_is_incomplete(monkeypatch):
    previous_state = SearchRequest(
        city="Baku",
        check_in=date(2026, 4, 20),
        check_out=date(2026, 4, 26),
        must_have_fields=[Field.KITCHEN],
    )

    async def _fake_route_conversation_async(**kwargs) -> ConversationRouteDecision:
        return ConversationRouteDecision(
            route="search_update",
            reason="user updates current search",
        )

    async def _fake_update_search_state(prev_state: SearchRequest, user_message: str) -> SearchRequest:
        return SearchRequest(
            city=None,
            check_in=prev_state.check_in,
            check_out=prev_state.check_out,
            must_have_fields=prev_state.must_have_fields,
        )

    monkeypatch.setattr(
        "app.logic.conversation_flow.route_conversation_async",
        _fake_route_conversation_async,
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
    
@pytest.mark.asyncio
async def test_conversation_flow_new_search_rebuilds_state(monkeypatch):
    previous_state = SearchRequest(city="Baku")

    async def _fake_route_conversation(**kwargs):
        from app.schemas.conversation_route import ConversationRouteDecision
        return ConversationRouteDecision(route="new_search")

    async def _fake_build_search_request(user_message):
        return SearchRequest(city="Paris")

    async def _fake_orchestrate_search(**kwargs):
        return {"need_clarification": False, "results": []}

    monkeypatch.setattr(
        "app.logic.conversation_flow.route_conversation_async",
        _fake_route_conversation,
    )
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
        "Now find me a hotel in Paris",
        previous_state=previous_state,
    )

    assert out["state"]["city"] == "Paris"
    
    
    
@pytest.mark.asyncio
async def test_conversation_flow_listing_question_returns_synchronized_legacy_state(monkeypatch):
    previous_state = SearchRequest(
        city="Baku",
        must_have_fields=[Field.KITCHEN],
        unknown_requests=["2 beds"],
    )

    async def _fake_route_conversation(**kwargs):
        from app.schemas.conversation_route import ConversationRouteDecision
        return ConversationRouteDecision(
            route="listing_question",
            reason="Question about shown listing",
        )

    async def _fake_answer_listing_question(**kwargs):
        from app.logic.conversation_flow import _build_state_payload

        return {
            "need_clarification": False,
            "response_type": "listing_question",
            "answer": "1 bed option is explicitly mentioned in the listing.",
            "state": _build_state_payload(previous_state),
        }

    monkeypatch.setattr(
        "app.logic.conversation_flow.route_conversation_async",
        _fake_route_conversation,
    )
    monkeypatch.setattr(
        "app.logic.conversation_flow._answer_listing_question",
        _fake_answer_listing_question,
    )

    from app.logic.conversation_flow import handle_user_message

    out = await handle_user_message(
        "Есть ли у этого отеля вариант с 1 кроватью?",
        previous_state=previous_state,
        shown_listing={"name": "Test Hotel"},
    )

    assert out["response_type"] == "listing_question"
    assert out["state"]["unknown_requests"] == ["2 beds"]
    assert any(c["normalized_text"] == "kitchen" for c in out["state"]["constraints"])
    assert any(c["normalized_text"] == "2 beds" for c in out["state"]["constraints"])


@pytest.mark.asyncio
async def test_conversation_flow_other_route_returns_synchronized_previous_state(monkeypatch):
    previous_state = SearchRequest(
        city="Baku",
        must_have_fields=[Field.KITCHEN],
        unknown_requests=["quiet neighborhood"],
    )

    async def _fake_route_conversation_async(**kwargs):
        from app.schemas.conversation_route import ConversationRouteDecision
        return ConversationRouteDecision(
            route="other",
            reason="not a search action",
        )

    monkeypatch.setattr(
        "app.logic.conversation_flow.route_conversation_async",
        _fake_route_conversation_async,
    )

    from app.logic.conversation_flow import handle_user_message

    out = await handle_user_message(
        "thanks",
        previous_state=previous_state,
    )

    assert out["response_type"] == "other"
    assert out["state"]["unknown_requests"] == ["quiet neighborhood"]
    assert any(c["normalized_text"] == "kitchen" for c in out["state"]["constraints"])
    assert any(c["normalized_text"] == "quiet neighborhood" for c in out["state"]["constraints"])
    assert out["parsed_intent"]["previous_state"]["unknown_requests"] == ["quiet neighborhood"]
    

    