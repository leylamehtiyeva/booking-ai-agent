from __future__ import annotations

from datetime import timedelta

from app.logic.request_resolution import parse_iso_date
from app.logic.request_resolution import parse_iso_date
from app.schemas.constraints import (
    ConstraintCategory,
    ConstraintMappingStatus,
    ConstraintPriority,
    EvidenceStrategy,
    UserConstraint,
)
from app.schemas.filters import PriceConstraint, SearchFilters
from app.schemas.intent_patch import SearchIntentPatch
from app.schemas.query import SearchRequest


def _unique(seq):
    seen = set()
    out = []
    for x in seq:
        key = x.value if hasattr(x, "value") else x
        if key not in seen:
            seen.add(key)
            out.append(x)
    return out


def _merge_price(
    current: PriceConstraint | None,
    incoming: PriceConstraint | None,
) -> PriceConstraint | None:
    if incoming is None:
        return current

    base = current.model_copy(deep=True) if current is not None else PriceConstraint()

    if incoming.min_amount is not None:
        base.min_amount = incoming.min_amount
    if incoming.max_amount is not None:
        base.max_amount = incoming.max_amount
    if incoming.currency is not None:
        base.currency = incoming.currency
    if incoming.scope is not None:
        base.scope = incoming.scope

    if (
        base.min_amount is None
        and base.max_amount is None
        and base.currency is None
        and base.scope is None
    ):
        return None

    return base


def _merge_filters(
    current: SearchFilters | None,
    incoming: SearchFilters | None,
) -> SearchFilters | None:
    if incoming is None:
        return current

    base = current.model_copy(deep=True) if current is not None else SearchFilters()

    if incoming.bedrooms_min is not None:
        base.bedrooms_min = incoming.bedrooms_min
    if incoming.bedrooms_max is not None:
        base.bedrooms_max = incoming.bedrooms_max

    if incoming.area_sqm_min is not None:
        base.area_sqm_min = incoming.area_sqm_min
    if incoming.area_sqm_max is not None:
        base.area_sqm_max = incoming.area_sqm_max

    if incoming.bathrooms_min is not None:
        base.bathrooms_min = incoming.bathrooms_min
    if incoming.bathrooms_max is not None:
        base.bathrooms_max = incoming.bathrooms_max

    base.price = _merge_price(base.price, incoming.price)

    data = base.model_dump(exclude_none=True)
    return base if data else None

def _constraint_text_key(text: str) -> str:
    return text.strip().casefold()


def _remove_constraints_by_text(
    constraints: list[UserConstraint],
    texts: list[str],
) -> list[UserConstraint]:
    if not texts:
        return constraints

    remove_keys = {_constraint_text_key(t) for t in texts if t and t.strip()}
    out: list[UserConstraint] = []

    for c in constraints:
        keys = {
            _constraint_text_key(c.raw_text),
            _constraint_text_key(c.normalized_text),
        }
        if keys & remove_keys:
            continue
        out.append(c)

    return out


def _dedupe_constraints(constraints: list[UserConstraint]) -> list[UserConstraint]:
    seen: set[tuple] = set()
    out: list[UserConstraint] = []

    for c in constraints:
        key = (
            c.priority.value,
            c.normalized_text.casefold(),
            tuple(field.value for field in c.mapped_fields),
            c.mapping_status.value,
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(c)

    return out





def apply_intent_patch(state: SearchRequest, patch: SearchIntentPatch) -> SearchRequest:
    data = state.model_copy(deep=True)


    # clear first
    if patch.clear_city:
        data.city = None

    if patch.clear_dates:
        data.check_in = None
        data.check_out = None

    if patch.clear_filters:
        data.filters = None
        
    if patch.set_adults is not None:
        data.adults = patch.set_adults

    if patch.set_children is not None:
        data.children = patch.set_children

    if patch.set_rooms is not None:
        data.rooms = patch.set_rooms

    # set scalar fields
    if patch.set_city:
        data.city = patch.set_city

    incoming_check_in = parse_iso_date(patch.set_check_in) if patch.set_check_in else None
    incoming_check_out = parse_iso_date(patch.set_check_out) if patch.set_check_out else None

    if incoming_check_in is not None and incoming_check_out is not None:
        data.check_in = incoming_check_in
        data.check_out = incoming_check_out

    elif incoming_check_in is not None:
        data.check_in = incoming_check_in

        if patch.set_nights is not None:
            if patch.set_nights > 0:
                data.check_out = data.check_in + timedelta(days=patch.set_nights)
            else:
                data.check_out = None
        else:
            data.check_out = data.check_in + timedelta(days=1)

    elif incoming_check_out is not None:
        data.check_out = incoming_check_out

    elif patch.set_nights is not None and data.check_in is not None:
        if patch.set_nights > 0:
            data.check_out = data.check_in + timedelta(days=patch.set_nights)
        else:
            data.check_out = None

    # ---- NEW SOURCE-OF-TRUTH PATCHING OVER CONSTRAINTS ----
    constraints = list(data.constraints or [])

    # direct removals from new patch API
    constraints = _remove_constraints_by_text(constraints, patch.remove_constraint_texts)


    # direct adds from new patch API
    constraints.extend(patch.add_constraints)


    data.constraints = _dedupe_constraints(constraints)

    # property types
    property_types = list(data.property_types or [])
    property_types = [x for x in property_types if x not in patch.remove_property_types]
    property_types.extend(patch.add_property_types)
    data.property_types = _unique(property_types) or None

    # occupancy types
    occupancy_types = list(data.occupancy_types or [])
    occupancy_types = [x for x in occupancy_types if x not in patch.remove_occupancy_types]
    occupancy_types.extend(patch.add_occupancy_types)
    data.occupancy_types = _unique(occupancy_types) or None
    
    # filters
    data.filters = _merge_filters(data.filters, patch.set_filters)


    return data