from app.logic.unresolved_constraint_utils import (
    get_unresolved_must_constraint_texts,
    get_unresolved_must_constraints,
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


def test_get_unresolved_must_constraints_returns_only_unresolved_must():
    request = SearchRequest(
        city="Baku",
        adults=2,
        children=0,
        rooms=1,
        constraints=[
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
            UserConstraint(
                raw_text="pet friendly",
                normalized_text="pet friendly",
                priority=ConstraintPriority.MUST,
                category=ConstraintCategory.POLICY,
                mapping_status=ConstraintMappingStatus.KNOWN,
                mapped_fields=[Field.PET_FRIENDLY],
                evidence_strategy=EvidenceStrategy.STRUCTURED,
            ),
        ],
    )

    constraints = get_unresolved_must_constraints(request)

    assert len(constraints) == 1
    assert constraints[0].normalized_text == "quiet neighborhood"


def test_get_unresolved_must_constraint_texts_dedupes():
    request = SearchRequest(
        city="Baku",
        adults=2,
        children=0,
        rooms=1,
        constraints=[
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
                raw_text="Quiet Neighborhood",
                normalized_text="quiet neighborhood",
                priority=ConstraintPriority.MUST,
                category=ConstraintCategory.LOCATION,
                mapping_status=ConstraintMappingStatus.UNRESOLVED,
                mapped_fields=[],
                evidence_strategy=EvidenceStrategy.TEXTUAL,
            ),
        ],
    )

    texts = get_unresolved_must_constraint_texts(request)

    assert texts == ["quiet neighborhood"]