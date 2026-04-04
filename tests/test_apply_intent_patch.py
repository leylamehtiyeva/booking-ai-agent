from datetime import date

from app.logic.apply_intent_patch import apply_intent_patch
from app.schemas.fields import Field
from app.schemas.filters import PriceConstraint, SearchFilters
from app.schemas.intent_patch import SearchIntentPatch
from app.schemas.query import SearchRequest


def test_set_nights_updates_checkout_from_existing_checkin():
    state = SearchRequest(
        user_message="test",
        city="Baku",
        check_in=date(2026, 4, 20),
        check_out=date(2026, 4, 21),
    )

    patch = SearchIntentPatch(set_nights=6)
    new_state = apply_intent_patch(state, patch)

    assert new_state.check_in == date(2026, 4, 20)
    assert new_state.check_out == date(2026, 4, 26)


def test_filter_merge_preserves_existing_fields():
    state = SearchRequest(
        user_message="test",
        city="Baku",
        filters=SearchFilters(bedrooms_min=2, area_sqm_min=80),
    )

    patch = SearchIntentPatch(
        set_filters=SearchFilters(bedrooms_min=3),
    )
    new_state = apply_intent_patch(state, patch)

    assert new_state.filters.bedrooms_min == 3
    assert new_state.filters.area_sqm_min == 80


def test_price_merge_preserves_other_price_fields():
    state = SearchRequest(
        user_message="test",
        city="Baku",
        filters=SearchFilters(
            price=PriceConstraint(max_amount=120, currency="USD", scope="per_night")
        ),
    )

    patch = SearchIntentPatch(
        set_filters=SearchFilters(
            price=PriceConstraint(max_amount=150)
        )
    )
    new_state = apply_intent_patch(state, patch)

    assert new_state.filters.price.max_amount == 150
    assert new_state.filters.price.currency == "USD"
    assert new_state.filters.price.scope == "per_night"


def test_add_and_remove_must_have_fields():
    state = SearchRequest(
        user_message="test",
        city="Baku",
        must_have_fields=[Field.KITCHEN, Field.PRIVATE_BATHROOM],
    )

    patch = SearchIntentPatch(
        add_must_have_fields=[Field.WIFI],
        remove_must_have_fields=[Field.KITCHEN],
    )
    new_state = apply_intent_patch(state, patch)

    assert Field.KITCHEN not in new_state.must_have_fields
    assert Field.PRIVATE_BATHROOM in new_state.must_have_fields
    assert Field.WIFI in new_state.must_have_fields


def test_clear_city_sets_city_to_none():
    state = SearchRequest(user_message="test", city="Baku")
    patch = SearchIntentPatch(clear_city=True)

    new_state = apply_intent_patch(state, patch)

    assert new_state.city is None