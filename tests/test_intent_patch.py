from app.logic.apply_intent_patch import apply_intent_patch
from app.schemas.fields import Field
from app.schemas.intent_patch import SearchIntentPatch
from app.schemas.query import SearchRequest


def test_add_must_have():
    state = SearchRequest(city="Baku")

    patch = SearchIntentPatch(add_must_have_fields=[Field.KITCHEN])

    new_state = apply_intent_patch(state, patch)

    assert Field.KITCHEN in new_state.must_have_fields
    assert any(
        c.normalized_text == "kitchen" and c.priority.value == "must"
        for c in new_state.constraints
    )


def test_remove_must_have():
    state = SearchRequest(
        city="Baku",
        must_have_fields=[Field.KITCHEN],
    )

    patch = SearchIntentPatch(remove_must_have_fields=[Field.KITCHEN])

    new_state = apply_intent_patch(state, patch)

    assert Field.KITCHEN not in new_state.must_have_fields
    assert all(c.normalized_text != "kitchen" for c in new_state.constraints)


def test_replace_city():
    state = SearchRequest(city="Baku")

    patch = SearchIntentPatch(set_city="Tbilisi")

    new_state = apply_intent_patch(state, patch)

    assert new_state.city == "Tbilisi"
    assert new_state.constraints == []
    
    
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
from app.logic.apply_intent_patch import apply_intent_patch


def test_add_constraints_updates_derived_legacy_fields():
    state = SearchRequest(city="Baku", adults=2, children=0, rooms=1)

    patch = SearchIntentPatch(
        add_constraints=[
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
        ]
    )

    new_state = apply_intent_patch(state, patch)

    assert len(new_state.constraints) == 2
    assert new_state.must_have_fields == [Field.KITCHEN]
    assert new_state.unknown_requests == ["quiet neighborhood"]


def test_remove_constraint_texts_removes_constraint_and_derived_fields():
    state = SearchRequest(
        city="Baku",
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
        ],
    )

    state = apply_intent_patch(state, SearchIntentPatch())  # force sync if needed
    patch = SearchIntentPatch(remove_constraint_texts=["kitchen"])

    new_state = apply_intent_patch(state, patch)

    assert all(c.normalized_text != "kitchen" for c in new_state.constraints)
    assert new_state.must_have_fields == []
    assert new_state.unknown_requests == ["quiet neighborhood"]


def test_legacy_patch_fields_are_converted_into_constraints():
    state = SearchRequest(city="Baku", adults=2, children=0, rooms=1)

    patch = SearchIntentPatch(
        add_must_have_fields=[Field.KETTLE],
        add_unknown_requests=["quiet area"],
    )

    new_state = apply_intent_patch(state, patch)

    assert any(c.normalized_text == "kettle" for c in new_state.constraints)
    assert any(c.normalized_text == "quiet area" for c in new_state.constraints)
    assert new_state.must_have_fields == [Field.KETTLE]
    assert new_state.unknown_requests == ["quiet area"]