from app.schemas.constraints import (
    ConstraintCategory,
    ConstraintMappingStatus,
    ConstraintPriority,
    EvidenceStrategy,
    UserConstraint,
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
    
    
