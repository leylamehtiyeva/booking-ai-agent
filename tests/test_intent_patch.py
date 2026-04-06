from app.logic.apply_intent_patch import apply_intent_patch
from app.schemas.fields import Field
from app.schemas.intent_patch import SearchIntentPatch
from app.schemas.query import SearchRequest


def test_add_must_have():
    state = SearchRequest(city="Baku")

    patch = SearchIntentPatch(add_must_have_fields=[Field.KITCHEN])

    new_state = apply_intent_patch(state, patch)

    assert Field.KITCHEN in new_state.must_have_fields


def test_remove_must_have():
    state = SearchRequest(
        city="Baku",
        must_have_fields=[Field.KITCHEN],
    )

    patch = SearchIntentPatch(remove_must_have_fields=[Field.KITCHEN])

    new_state = apply_intent_patch(state, patch)

    assert Field.KITCHEN not in new_state.must_have_fields


def test_replace_city():
    state = SearchRequest(city="Baku")

    patch = SearchIntentPatch(set_city="Tbilisi")

    new_state = apply_intent_patch(state, patch)

    assert new_state.city == "Tbilisi"