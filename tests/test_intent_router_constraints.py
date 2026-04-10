import asyncio

from app.agents.intent_router_agent import IntentRoute
from app.logic.intent_router import (
    _lift_legacy_unknown_requests_into_constraints,
    build_search_request_adk_async,
)
from app.schemas.constraints import (
    ConstraintCategory,
    ConstraintMappingStatus,
    ConstraintPriority,
    EvidenceStrategy,
    UserConstraint,
)
from app.schemas.fields import Field
from app.schemas.filters import SearchFilters
from app.schemas.property_semantics import PropertyType


def test_build_search_request_uses_constraints_as_source_of_truth(monkeypatch):
    parsed_intent = IntentRoute(
        city="Baku",
        check_in="2026-04-10",
        check_out="2026-04-15",
        adults=4,
        children=0,
        rooms=1,
        filters=SearchFilters(),
        property_types=[PropertyType.APARTMENT],
        occupancy_types=[],
        constraints=[
            UserConstraint(
                raw_text="place for cooking",
                normalized_text="place for cooking",
                priority=ConstraintPriority.MUST,
                category=ConstraintCategory.AMENITY,
                mapping_status=ConstraintMappingStatus.KNOWN,
                mapped_fields=[Field.KITCHEN],
                evidence_strategy=EvidenceStrategy.STRUCTURED,
            ),
            UserConstraint(
                raw_text="quiet neighborhood",
                normalized_text="quiet neighborhood",
                priority=ConstraintPriority.MUST,
                category=ConstraintCategory.LOCATION,
                mapping_status=ConstraintMappingStatus.UNRESOLVED,
                mapped_fields=[],
                evidence_strategy=EvidenceStrategy.TEXTUAL,
            ),
            UserConstraint(
                raw_text="balcony",
                normalized_text="balcony",
                priority=ConstraintPriority.NICE,
                category=ConstraintCategory.AMENITY,
                mapping_status=ConstraintMappingStatus.KNOWN,
                mapped_fields=[Field.BALCONY],
                evidence_strategy=EvidenceStrategy.STRUCTURED,
            ),
        ],
    )

    async def fake_route_intent_adk_async(user_text: str):
        return parsed_intent

    monkeypatch.setattr(
        "app.logic.intent_router.route_intent_adk_async",
        fake_route_intent_adk_async,
    )

    req = asyncio.run(
        build_search_request_adk_async(
            "I want an apartment in Baku from 10 to 15 April for 4 people with a place for cooking"
        )
    )

    assert len(req.constraints) == len(parsed_intent.constraints)

    # проверяем canonicalization
    assert req.constraints[0].normalized_text == "kitchen"
    assert req.constraints[0].mapped_fields == [Field.KITCHEN]

    # unresolved остаётся как есть
    assert req.constraints[1].normalized_text == "quiet neighborhood"
    assert req.constraints[1].mapping_status == ConstraintMappingStatus.UNRESOLVED

    # nice constraint
    assert req.constraints[2].normalized_text == "balcony"
    assert req.constraints[2].priority == ConstraintPriority.NICE
    assert req.must_have_fields == [Field.KITCHEN]
    assert req.nice_to_have_fields == [Field.BALCONY]
    assert req.forbidden_fields == []
    assert req.unknown_requests == ["quiet neighborhood"]
    assert req.property_types == [PropertyType.APARTMENT]


def test_lift_legacy_unknown_requests_into_constraints_when_constraints_are_missing():
    payload = {
        "city": "Baku",
        "check_in": "2026-04-10",
        "check_out": "2026-04-15",
        "constraints": [],
        "unknown_requests": ["quiet neighborhood", "quiet neighborhood"],
    }

    out = _lift_legacy_unknown_requests_into_constraints(payload)

    assert len(out["constraints"]) == 1
    c0 = out["constraints"][0]

    assert c0["raw_text"] == "quiet neighborhood"
    assert c0["normalized_text"] == "quiet neighborhood"
    assert c0["priority"] == "must"
    assert c0["category"] == "other"
    assert c0["mapping_status"] == "unresolved"
    assert c0["mapped_fields"] == []
    assert c0["evidence_strategy"] == "textual"


def test_lift_legacy_unknown_requests_does_not_override_existing_constraints():
    payload = {
        "city": "Baku",
        "constraints": [
            {
                "raw_text": "balcony",
                "normalized_text": "balcony",
                "priority": "nice",
                "category": "amenity",
                "mapping_status": "known",
                "mapped_fields": ["balcony"],
                "evidence_strategy": "structured",
            }
        ],
        "unknown_requests": ["quiet neighborhood"],
    }

    out = _lift_legacy_unknown_requests_into_constraints(payload)

    assert len(out["constraints"]) == 1
    assert out["constraints"][0]["normalized_text"] == "balcony"