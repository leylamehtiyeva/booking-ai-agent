from copy import deepcopy

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


def apply_intent_patch(state: SearchRequest, patch: SearchIntentPatch) -> SearchRequest:
    data = state.model_copy(deep=True)

    # --- city ---
    if patch.clear_city:
        data.city = None
    elif patch.set_city:
        data.city = patch.set_city

    # --- dates ---
    if patch.clear_dates:
        data.check_in = None
        data.check_out = None
    else:
        if patch.set_check_in:
            data.check_in = patch.set_check_in
        if patch.set_check_out:
            data.check_out = patch.set_check_out

    # --- must-have ---
    must = list(data.must_have_fields or [])
    must = [x for x in must if x not in patch.remove_must_have_fields]
    must.extend(patch.add_must_have_fields)
    data.must_have_fields = _unique(must)

    # --- nice-to-have ---
    nice = list(data.nice_to_have_fields or [])
    nice = [x for x in nice if x not in patch.remove_nice_to_have_fields]
    nice.extend(patch.add_nice_to_have_fields)
    data.nice_to_have_fields = _unique(nice)

    # --- forbidden ---
    forbidden = list(data.forbidden_fields or [])
    forbidden = [x for x in forbidden if x not in patch.remove_forbidden_fields]
    forbidden.extend(patch.add_forbidden_fields)
    data.forbidden_fields = _unique(forbidden)

    # --- consistency ---
    data.nice_to_have_fields = [
        x for x in data.nice_to_have_fields if x not in data.must_have_fields
    ]
    data.must_have_fields = [
        x for x in data.must_have_fields if x not in data.forbidden_fields
    ]
    data.nice_to_have_fields = [
        x for x in data.nice_to_have_fields if x not in data.forbidden_fields
    ]

    # --- filters ---
    if patch.clear_filters:
        data.filters = None
    elif patch.set_filters is not None:
        data.filters = patch.set_filters

    return data