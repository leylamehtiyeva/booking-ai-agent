from app.schemas.constraints import (
    ConstraintCategory,
    ConstraintMappingStatus,
    ConstraintPriority,
    EvidenceStrategy,
    UserConstraint,
)
from app.logic.constraint_state import (
    build_constraints_from_legacy_state,
    build_legacy_state_from_constraints,
    sync_constraints_from_legacy_state,
    sync_legacy_state_from_constraints,
)


from app.schemas.fields import Field
from app.schemas.query import SearchRequest


def test_user_constraint_defaults():
    constraint = UserConstraint(
        raw_text="place for cooking",
        normalized_text="place for cooking",
        priority=ConstraintPriority.MUST,
    )

    assert constraint.id
    assert constraint.priority == ConstraintPriority.MUST
    assert constraint.category == ConstraintCategory.OTHER
    assert constraint.mapping_status == ConstraintMappingStatus.UNRESOLVED
    assert constraint.mapped_fields == []
    assert constraint.evidence_strategy == EvidenceStrategy.NONE


def test_user_constraint_can_store_known_mapping():
    constraint = UserConstraint(
        raw_text="place for cooking",
        normalized_text="place for cooking",
        priority=ConstraintPriority.MUST,
        category=ConstraintCategory.AMENITY,
        mapping_status=ConstraintMappingStatus.KNOWN,
        mapped_fields=[Field.KITCHEN],
        evidence_strategy=EvidenceStrategy.STRUCTURED,
    )

    assert constraint.mapping_status == ConstraintMappingStatus.KNOWN
    assert constraint.mapped_fields == [Field.KITCHEN]
    assert constraint.evidence_strategy == EvidenceStrategy.STRUCTURED


def test_search_request_has_constraints_list():
    request = SearchRequest(city="Baku")

    assert request.constraints == []


def test_search_request_accepts_constraints():
    constraint = UserConstraint(
        raw_text="pet friendly",
        normalized_text="pet friendly",
        priority=ConstraintPriority.MUST,
        category=ConstraintCategory.POLICY,
        mapping_status=ConstraintMappingStatus.KNOWN,
        mapped_fields=[Field.PET_FRIENDLY],
        evidence_strategy=EvidenceStrategy.STRUCTURED,
    )

    request = SearchRequest(
        city="Baku",
        constraints=[constraint],
    )

    assert len(request.constraints) == 1
    assert request.constraints[0].raw_text == "pet friendly"
    assert request.constraints[0].mapped_fields == [Field.PET_FRIENDLY]
    
def test_build_legacy_state_from_constraints_known_and_unresolved():
    constraints = [
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
            raw_text="balcony",
            normalized_text="balcony",
            priority=ConstraintPriority.NICE,
            category=ConstraintCategory.AMENITY,
            mapping_status=ConstraintMappingStatus.KNOWN,
            mapped_fields=[Field.BALCONY],
            evidence_strategy=EvidenceStrategy.STRUCTURED,
        ),
        UserConstraint(
            raw_text="smoking allowed",
            normalized_text="smoking allowed",
            priority=ConstraintPriority.FORBIDDEN,
            category=ConstraintCategory.POLICY,
            mapping_status=ConstraintMappingStatus.KNOWN,
            mapped_fields=[Field.SMOKING_ALLOWED],
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
            raw_text="city center",
            normalized_text="city center",
            priority=ConstraintPriority.NICE,
            category=ConstraintCategory.LOCATION,
            mapping_status=ConstraintMappingStatus.UNRESOLVED,
            mapped_fields=[],
            evidence_strategy=EvidenceStrategy.GEO,
        ),
    ]

    legacy = build_legacy_state_from_constraints(constraints)

    assert legacy["must_have_fields"] == [Field.KITCHEN]
    assert legacy["nice_to_have_fields"] == [Field.BALCONY]
    assert legacy["forbidden_fields"] == [Field.SMOKING_ALLOWED]
    assert legacy["unknown_requests"] == ["quiet neighborhood"]


def test_sync_legacy_state_from_constraints_sets_compatibility_fields():
    request = SearchRequest(
        city="Baku",
        constraints=[
            UserConstraint(
                raw_text="pet friendly",
                normalized_text="pet friendly",
                priority=ConstraintPriority.MUST,
                category=ConstraintCategory.POLICY,
                mapping_status=ConstraintMappingStatus.KNOWN,
                mapped_fields=[Field.PET_FRIENDLY],
                evidence_strategy=EvidenceStrategy.STRUCTURED,
            ),
            UserConstraint(
                raw_text="quiet area",
                normalized_text="quiet area",
                priority=ConstraintPriority.MUST,
                category=ConstraintCategory.LOCATION,
                mapping_status=ConstraintMappingStatus.UNRESOLVED,
                mapped_fields=[],
                evidence_strategy=EvidenceStrategy.TEXTUAL,
            ),
        ],
    )

    synced = sync_legacy_state_from_constraints(request)

    assert synced.must_have_fields == [Field.PET_FRIENDLY]
    assert synced.nice_to_have_fields == []
    assert synced.forbidden_fields == []
    assert synced.unknown_requests == ["quiet area"]
    
    
