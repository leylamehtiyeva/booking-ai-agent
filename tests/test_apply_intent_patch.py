from datetime import date

from app.logic.apply_intent_patch import apply_intent_patch
from app.schemas.fields import Field
from app.schemas.filters import PriceConstraint, SearchFilters
from app.schemas.intent_patch import SearchIntentPatch
from app.schemas.query import SearchRequest


def test_set_nights_updates_checkout_from_existing_checkin():
    state = SearchRequest(
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
    state = SearchRequest(city="Baku")
    patch = SearchIntentPatch(clear_city=True)

    new_state = apply_intent_patch(state, patch)

    assert new_state.city is None
    
    
from app.logic.apply_intent_patch import apply_intent_patch
from app.schemas.intent_patch import SearchIntentPatch
from app.schemas.query import SearchRequest


def test_apply_patch_updates_adults_children_and_rooms():
    state = SearchRequest(
        city="Baku",
        adults=2,
        children=0,
        rooms=1,
    )

    patch = SearchIntentPatch(
        set_adults=3,
        set_children=1,
        set_rooms=2,
    )

    new_state = apply_intent_patch(state, patch)

    assert new_state.adults == 3
    assert new_state.children == 1
    assert new_state.rooms == 2
    
    
def test_apply_patch_updates_only_adults_without_touching_other_fields():
    state = SearchRequest(
        city="Baku",
        adults=2,
        children=1,
        rooms=1,
    )

    patch = SearchIntentPatch(set_adults=4)

    new_state = apply_intent_patch(state, patch)

    assert new_state.adults == 4
    assert new_state.children == 1
    assert new_state.rooms == 1
    
    
def test_apply_patch_adds_unknown_requests():
    state = SearchRequest(
        city="Baku",
        unknown_requests=[],
    )

    patch = SearchIntentPatch(
        add_unknown_requests=["2 beds"],
    )

    new_state = apply_intent_patch(state, patch)

    assert any(c.normalized_text == "2 beds" for c in new_state.constraints)
    assert new_state.unknown_requests == ["2 beds"]


def test_apply_patch_removes_unknown_requests():
    state = SearchRequest(
        city="Baku",
        unknown_requests=["2 beds", "satellite TV"],
    )

    patch = SearchIntentPatch(
        remove_unknown_requests=["2 beds"],
    )

    new_state = apply_intent_patch(state, patch)

    assert all(c.normalized_text != "2 beds" for c in new_state.constraints)
    assert new_state.unknown_requests == ["satellite TV"]
    
    
def test_set_check_in_only_recomputes_checkout_to_one_night():
    state = SearchRequest(
        city="Baku",
        check_in=date(2026, 4, 20),
        check_out=date(2026, 4, 26),
    )

    patch = SearchIntentPatch(set_check_in="2026-04-08")
    new_state = apply_intent_patch(state, patch)

    assert new_state.check_in == date(2026, 4, 8)
    assert new_state.check_out == date(2026, 4, 9)
    
    
def test_set_check_in_with_nights_recomputes_checkout():
    state = SearchRequest(
        city="Baku",
        check_in=date(2026, 4, 20),
        check_out=date(2026, 4, 26),
    )

    patch = SearchIntentPatch(set_check_in="2026-04-08", set_nights=4)
    new_state = apply_intent_patch(state, patch)

    assert new_state.check_in == date(2026, 4, 8)
    assert new_state.check_out == date(2026, 4, 12)