from app.logic.constraint_state import (
    build_constraints_from_legacy_state,
    build_legacy_state_from_constraints,
    sync_constraints_from_legacy_state,
)
from app.schemas.constraints import (
    ConstraintCategory,
    ConstraintMappingStatus,
    ConstraintPriority,
    EvidenceStrategy,
    UserConstraint,
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


def test_build_legacy_state_from_constraints_projects_only_unresolved_must():
    request = SearchRequest(
        constraints=[
            UserConstraint(
                raw_text="place for cooking",
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
            UserConstraint(
                raw_text="balcony if possible",
                normalized_text="balcony if possible",
                priority=ConstraintPriority.NICE,
                category=ConstraintCategory.AMENITY,
                mapping_status=ConstraintMappingStatus.UNRESOLVED,
                mapped_fields=[],
                evidence_strategy=EvidenceStrategy.TEXTUAL,
            ),
            UserConstraint(
                raw_text="no noisy street",
                normalized_text="no noisy street",
                priority=ConstraintPriority.FORBIDDEN,
                category=ConstraintCategory.LOCATION,
                mapping_status=ConstraintMappingStatus.UNRESOLVED,
                mapped_fields=[],
                evidence_strategy=EvidenceStrategy.TEXTUAL,
            ),
        ]
    )

    legacy = build_legacy_state_from_constraints(request.constraints)

    assert legacy["must_have_fields"] == [Field.KITCHEN]
    assert legacy["nice_to_have_fields"] == []
    assert legacy["forbidden_fields"] == []
    assert legacy["unknown_requests"] == ["quiet neighborhood"]