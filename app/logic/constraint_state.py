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

    return _dedupe_constraints(constraints)


def sync_constraints_from_legacy_state(request: SearchRequest) -> SearchRequest:
    updated = request.model_copy(deep=True)
    updated.constraints = build_constraints_from_legacy_state(updated)
    return updated


def build_legacy_state_from_constraints(
    constraints: list[UserConstraint],
) -> dict[str, list[Field] | list[str]]:
    """
    Build the legacy field-centric projection from canonical constraints.

    IMPORTANT:
    - constraints is the only source of truth.
    - This projection is intentionally lossy and exists only for backward
      compatibility, debug output, and legacy UI/integration layers.
    - unknown_requests is NOT a full representation of unresolved constraints;
      it currently includes only unresolved MUST constraints.
    - New logic must never rely on this projection when constraints are available.
    """
    must_have_fields: list[Field] = []
    nice_to_have_fields: list[Field] = []
    forbidden_fields: list[Field] = []
    unknown_requests: list[str] = []

    for constraint in constraints:
        if constraint.mapping_status == ConstraintMappingStatus.KNOWN and constraint.mapped_fields:
            if constraint.priority == ConstraintPriority.MUST:
                must_have_fields.extend(constraint.mapped_fields)
            elif constraint.priority == ConstraintPriority.NICE:
                nice_to_have_fields.extend(constraint.mapped_fields)
            elif constraint.priority == ConstraintPriority.FORBIDDEN:
                forbidden_fields.extend(constraint.mapped_fields)
            continue

        # Compatibility-only projection:
        # legacy unknown_requests historically behaved like unresolved MUST items.
        # We keep that behavior for backward compatibility, but this must never be
        # interpreted as the full unresolved constraint state.
        if (
            constraint.mapping_status == ConstraintMappingStatus.UNRESOLVED
            and constraint.priority == ConstraintPriority.MUST
            and constraint.normalized_text.strip()
        ):
            unknown_requests.append(constraint.normalized_text.strip())

    must_have_fields = _dedupe_fields(must_have_fields)
    nice_to_have_fields = _dedupe_fields(
        [field for field in nice_to_have_fields if field not in must_have_fields]
    )
    forbidden_fields = _dedupe_fields(forbidden_fields)

    must_have_fields = [field for field in must_have_fields if field not in forbidden_fields]
    nice_to_have_fields = [field for field in nice_to_have_fields if field not in forbidden_fields]
    unknown_requests = _dedupe_strings(unknown_requests)

    return {
        "must_have_fields": must_have_fields,
        "nice_to_have_fields": nice_to_have_fields,
        "forbidden_fields": forbidden_fields,
        "unknown_requests": unknown_requests,
    }


def sync_legacy_state_from_constraints(request: SearchRequest) -> SearchRequest:
    """
    Refresh the legacy compatibility layer from canonical constraints.

    After this call, must_have_fields / nice_to_have_fields / forbidden_fields /
    unknown_requests are derived views only.
    """
    updated = request.model_copy(deep=True)
    legacy = build_legacy_state_from_constraints(updated.constraints)

    updated.must_have_fields = legacy["must_have_fields"]
    updated.nice_to_have_fields = legacy["nice_to_have_fields"]
    updated.forbidden_fields = legacy["forbidden_fields"]
    updated.unknown_requests = legacy["unknown_requests"]
    return updated