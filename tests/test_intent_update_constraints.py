import pytest
from datetime import date

from app.logic.intent_update import (
    _build_update_prompt,
    _canonicalize_patch,
    update_search_state_async,
)
from app.schemas.constraints import (
    ConstraintCategory,
    ConstraintMappingStatus,
    ConstraintPriority,
    EvidenceStrategy,
    UserConstraint,
)
from app.schemas.fields import Field
from app.schemas.intent_patch import SearchIntentPatch
from app.schemas.query import SearchRequest


def test_build_update_prompt_includes_constraints_for_legacy_state():
    previous_state = SearchRequest(
        city="Baku",
        check_in=date(2026, 4, 20),
        check_out=date(2026, 4, 26),
        adults=2,
        children=0,
        rooms=1,
        must_have_fields=[Field.KITCHEN],
        unknown_requests=["quiet neighborhood"],
    )

    prompt = _build_update_prompt(previous_state, "also add a balcony")

    assert '"constraints"' in prompt
    assert '"normalized_text": "kitchen"' in prompt
    assert '"normalized_text": "quiet neighborhood"' in prompt


def test_canonicalize_patch_lifts_legacy_unknown_patch_fields():
    patch = SearchIntentPatch(
        add_unknown_requests=["quiet neighborhood"],
        remove_unknown_requests=["satellite TV"],
    )

    out = _canonicalize_patch(patch)

    assert out.add_unknown_requests == []
    assert out.remove_unknown_requests == []
    assert out.remove_constraint_texts == ["satellite TV"]

    assert len(out.add_constraints) == 1
    c0 = out.add_constraints[0]
    assert c0.normalized_text == "quiet neighborhood"
    assert c0.priority == ConstraintPriority.MUST
    assert c0.mapping_status == ConstraintMappingStatus.UNRESOLVED


@pytest.mark.asyncio
async def test_update_search_state_async_preserves_constraint_centric_state(monkeypatch):
    previous_state = SearchRequest(
        city="Baku",
        check_in=date(2026, 4, 20),
        check_out=date(2026, 4, 26),
        adults=2,
        children=0,
        rooms=1,
        constraints=[
            UserConstraint(
                raw_text="kitchen",
                normalized_text="kitchen",
                priority=ConstraintPriority.MUST,
                category=ConstraintCategory.AMENITY,
                mapping_status=ConstraintMappingStatus.KNOWN,
                mapped_fields=[Field.KITCHEN],
                evidence_strategy=EvidenceStrategy.STRUCTURED,
            )
        ],
    )

    async def fake_route_intent_update_patch_async(previous_state, user_message):
        return SearchIntentPatch(
            add_constraints=[
                UserConstraint(
                    raw_text="quiet neighborhood",
                    normalized_text="quiet neighborhood",
                    priority=ConstraintPriority.MUST,
                    category=ConstraintCategory.LOCATION,
                    mapping_status=ConstraintMappingStatus.UNRESOLVED,
                    mapped_fields=[],
                    evidence_strategy=EvidenceStrategy.TEXTUAL,
                )
            ]
        )

    monkeypatch.setattr(
        "app.logic.intent_update.route_intent_update_patch_async",
        fake_route_intent_update_patch_async,
    )

    new_state = await update_search_state_async(
        previous_state,
        "also I want a quiet neighborhood",
    )

    assert any(c.normalized_text == "kitchen" for c in new_state.constraints)
    assert any(c.normalized_text == "quiet neighborhood" for c in new_state.constraints)
    assert new_state.must_have_fields == [Field.KITCHEN]
    assert new_state.unknown_requests == ["quiet neighborhood"]


@pytest.mark.asyncio
async def test_update_search_state_async_upgrades_legacy_previous_state(monkeypatch):
    previous_state = SearchRequest(
        city="Baku",
        check_in=date(2026, 4, 20),
        check_out=date(2026, 4, 26),
        adults=2,
        children=0,
        rooms=1,
        must_have_fields=[Field.KITCHEN],
        unknown_requests=["quiet neighborhood"],
    )

    async def fake_route_intent_update_patch_async(previous_state, user_message):
        # previous_state passed into the route layer should already contain constraints
        assert any(c.normalized_text == "kitchen" for c in previous_state.constraints)
        assert any(c.normalized_text == "quiet neighborhood" for c in previous_state.constraints)
        return SearchIntentPatch()

    monkeypatch.setattr(
        "app.logic.intent_update.route_intent_update_patch_async",
        fake_route_intent_update_patch_async,
    )

    new_state = await update_search_state_async(
        previous_state,
        "no changes",
    )

    assert any(c.normalized_text == "kitchen" for c in new_state.constraints)
    assert any(c.normalized_text == "quiet neighborhood" for c in new_state.constraints)


@pytest.mark.asyncio
async def test_update_search_state_async_legacy_unknown_patch_is_canonicalized(monkeypatch):
    previous_state = SearchRequest(
        city="Baku",
        check_in=date(2026, 4, 20),
        check_out=date(2026, 4, 26),
        adults=2,
        children=0,
        rooms=1,
        constraints=[],
    )

    async def fake_route_intent_update_patch_async(previous_state, user_message):
        return SearchIntentPatch(
            add_unknown_requests=["quiet neighborhood"],
            remove_unknown_requests=["satellite TV"],
        )

    monkeypatch.setattr(
        "app.logic.intent_update.route_intent_update_patch_async",
        fake_route_intent_update_patch_async,
    )

    new_state = await update_search_state_async(
        previous_state,
        "also quiet neighborhood, no need for satellite TV",
    )

    assert any(c.normalized_text == "quiet neighborhood" for c in new_state.constraints)
    assert all(c.normalized_text != "satellite TV" for c in new_state.constraints)
    assert new_state.unknown_requests == ["quiet neighborhood"]