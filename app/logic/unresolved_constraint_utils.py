from __future__ import annotations

from app.schemas.constraints import ConstraintMappingStatus, ConstraintPriority, UserConstraint
from app.schemas.query import SearchRequest


def get_unresolved_must_constraints(request: SearchRequest) -> list[UserConstraint]:
    constraints = request.constraints or []
    return [
        c
        for c in constraints
        if c.priority == ConstraintPriority.MUST
        and c.mapping_status == ConstraintMappingStatus.UNRESOLVED
        and c.normalized_text.strip()
    ]


def get_unresolved_must_constraint_texts(request: SearchRequest) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    for c in get_unresolved_must_constraints(request):
        text = c.normalized_text.strip()
        key = text.casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(text)

    return out