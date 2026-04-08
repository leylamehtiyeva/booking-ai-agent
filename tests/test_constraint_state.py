from app.logic.constraint_state import (
    build_constraints_from_legacy_state,
    sync_constraints_from_legacy_state,
)
from app.schemas.constraints import (
    ConstraintCategory,
    ConstraintMappingStatus,
    ConstraintPriority,
    EvidenceStrategy,
)
from app.schemas.fields import Field
from app.schemas.query import SearchRequest


def test_build_constraints_from_legacy_known_and_unknown():
    request = SearchRequest(
        city="Baku",
        must_have_fields=[Field.KITCHEN],
        nice_to_have_fields=[Field.BALCONY],
        forbidden_fields=[Field.SMOKING_ALLOWED],
        unknown_requests=["quiet neighborhood"],
    )

    constraints = build_constraints_from_legacy_state(request)

    assert len(constraints) == 4

    kitchen = next(c for c in constraints if c.normalized_text == "kitchen")
    assert kitchen.priority == ConstraintPriority.MUST
    assert kitchen.mapping_status == ConstraintMappingStatus.KNOWN
    assert kitchen.mapped_fields == [Field.KITCHEN]
    assert kitchen.category == ConstraintCategory.AMENITY
    assert kitchen.evidence_strategy == EvidenceStrategy.STRUCTURED

    balcony = next(c for c in constraints if c.normalized_text == "balcony")
    assert balcony.priority == ConstraintPriority.NICE

    smoking = next(c for c in constraints if c.normalized_text == "smoking_allowed")
    assert smoking.priority == ConstraintPriority.FORBIDDEN

    quiet = next(c for c in constraints if c.normalized_text == "quiet neighborhood")
    assert quiet.priority == ConstraintPriority.MUST
    assert quiet.mapping_status == ConstraintMappingStatus.UNRESOLVED
    assert quiet.mapped_fields == []
    assert quiet.evidence_strategy == EvidenceStrategy.TEXTUAL


def test_build_constraints_dedupes_duplicates():
    request = SearchRequest(
        city="Baku",
        must_have_fields=[Field.KITCHEN, Field.KITCHEN],
        unknown_requests=["sea view", "sea view"],
    )

    constraints = build_constraints_from_legacy_state(request)

    assert len(constraints) == 2
    normalized_texts = sorted(c.normalized_text for c in constraints)
    assert normalized_texts == ["kitchen", "sea view"]


def test_sync_constraints_from_legacy_state_sets_request_constraints():
    request = SearchRequest(
        city="Baku",
        must_have_fields=[Field.KETTLE],
        unknown_requests=["quiet area"],
    )

    synced = sync_constraints_from_legacy_state(request)

    assert len(synced.constraints) == 2
    assert any(c.normalized_text == "kettle" for c in synced.constraints)
    assert any(c.normalized_text == "quiet area" for c in synced.constraints)