from __future__ import annotations

from app.schemas.constraints import (
    ConstraintCategory,
    ConstraintMappingStatus,
    ConstraintPriority,
    EvidenceStrategy,
    UserConstraint,
)
from app.schemas.fields import Field
from app.schemas.query import SearchRequest


_FIELD_CATEGORY_MAP: dict[Field, ConstraintCategory] = {
    # cooking
    Field.KITCHEN: ConstraintCategory.AMENITY,
    Field.KITCHENETTE: ConstraintCategory.AMENITY,
    Field.STOVE_OR_HOB: ConstraintCategory.AMENITY,
    Field.OVEN: ConstraintCategory.AMENITY,
    Field.MICROWAVE: ConstraintCategory.AMENITY,
    Field.REFRIGERATOR: ConstraintCategory.AMENITY,
    Field.COOKWARE: ConstraintCategory.AMENITY,
    Field.KETTLE: ConstraintCategory.AMENITY,
    Field.COFFEE_MACHINE: ConstraintCategory.AMENITY,
    # bathroom
    Field.PRIVATE_BATHROOM: ConstraintCategory.AMENITY,
    Field.BATHTUB: ConstraintCategory.AMENITY,
    Field.SHOWER: ConstraintCategory.AMENITY,
    Field.HOT_WATER: ConstraintCategory.AMENITY,
    Field.TOWELS: ConstraintCategory.AMENITY,
    Field.HAIR_DRYER: ConstraintCategory.AMENITY,
    Field.TOILETRIES: ConstraintCategory.AMENITY,
    # comfort / living
    Field.WIFI: ConstraintCategory.AMENITY,
    Field.AIR_CONDITIONING: ConstraintCategory.AMENITY,
    Field.HEATING: ConstraintCategory.AMENITY,
    Field.WASHING_MACHINE: ConstraintCategory.AMENITY,
    Field.DRYER: ConstraintCategory.AMENITY,
    Field.IRON: ConstraintCategory.AMENITY,
    Field.WORKSPACE: ConstraintCategory.AMENITY,
    Field.ELEVATOR: ConstraintCategory.AMENITY,
    Field.BALCONY: ConstraintCategory.AMENITY,
    # policies
    Field.NON_SMOKING: ConstraintCategory.POLICY,
    Field.FREE_CANCELLATION: ConstraintCategory.POLICY,
    Field.PAY_AT_PROPERTY: ConstraintCategory.POLICY,
    Field.PET_FRIENDLY: ConstraintCategory.POLICY,
    Field.SMOKING_ALLOWED: ConstraintCategory.POLICY,
    Field.PARTIES_ALLOWED: ConstraintCategory.POLICY,
    Field.CHILDREN_ALLOWED: ConstraintCategory.POLICY,
    Field.PARKING: ConstraintCategory.POLICY,
}



def _field_category(field: Field) -> ConstraintCategory:
    return _FIELD_CATEGORY_MAP.get(field, ConstraintCategory.OTHER)


def _known_constraint(field: Field, priority: ConstraintPriority) -> UserConstraint:
    return UserConstraint(
        raw_text=field.value,
        normalized_text=field.value,
        priority=priority,
        category=_field_category(field),
        mapping_status=ConstraintMappingStatus.KNOWN,
        mapped_fields=[field],
        evidence_strategy=EvidenceStrategy.STRUCTURED,
    )


def _unknown_constraint(text: str) -> UserConstraint:
    normalized = text.strip()
    return UserConstraint(
        raw_text=text,
        normalized_text=normalized,
        priority=ConstraintPriority.MUST,
        category=ConstraintCategory.OTHER,
        mapping_status=ConstraintMappingStatus.UNRESOLVED,
        mapped_fields=[],
        evidence_strategy=EvidenceStrategy.TEXTUAL,
    )

def _canonicalize_constraints(constraints: list[UserConstraint]) -> list[UserConstraint]:
    out: list[UserConstraint] = []

    for constraint in constraints:
        if (
            constraint.mapping_status == ConstraintMappingStatus.KNOWN
            and constraint.mapped_fields
        ):
            canonical = constraint.mapped_fields[0].value
            constraint = constraint.model_copy(
                update={"normalized_text": canonical}
            )

        out.append(constraint)

    return out

def _dedupe_constraints(constraints: list[UserConstraint]) -> list[UserConstraint]:
    seen: set[tuple] = set()
    out: list[UserConstraint] = []

    for constraint in constraints:
        key = (
            constraint.priority.value,
            constraint.normalized_text.casefold(),
            tuple(field.value for field in constraint.mapped_fields),
            constraint.mapping_status.value,
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(constraint)

    return out


def _dedupe_fields(fields: list[Field]) -> list[Field]:
    out: list[Field] = []
    seen: set[Field] = set()
    for field in fields:
        if field in seen:
            continue
        seen.add(field)
        out.append(field)
    return out


def _dedupe_strings(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(value.strip())
    return out


def build_constraints_from_legacy_state(request: SearchRequest) -> list[UserConstraint]:
    """
    Lift legacy field-centric state into canonical constraint-centric state.

    This function exists so older payloads and tests can still enter the system,
    but downstream logic should treat the returned constraints as the semantic
    source of truth.
    """
    constraints: list[UserConstraint] = []

    for field in request.must_have_fields:
        constraints.append(_known_constraint(field, ConstraintPriority.MUST))

    for field in request.nice_to_have_fields:
        constraints.append(_known_constraint(field, ConstraintPriority.NICE))

    for field in request.forbidden_fields:
        constraints.append(_known_constraint(field, ConstraintPriority.FORBIDDEN))

    for text in request.unknown_requests:
        if text and text.strip():
            constraints.append(_unknown_constraint(text))

    constraints = _canonicalize_constraints(constraints)
    return _dedupe_constraints(constraints)


def sync_constraints_from_legacy_state(request: SearchRequest) -> SearchRequest:
    updated = request.model_copy(deep=True)
    updated.constraints = build_constraints_from_legacy_state(updated)
    return updated


