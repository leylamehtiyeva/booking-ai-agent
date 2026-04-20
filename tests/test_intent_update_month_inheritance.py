from app.logic.intent_update import _inherit_month_from_previous_state
from app.schemas.intent_patch import SearchIntentPatch
from app.schemas.query import SearchRequest


def test_followup_month_inheritance_is_temporarily_disabled_for_partial_update():
    previous_state = SearchRequest(
        city="Baku",
        check_in="2026-04-20",
        check_out="2026-04-25",
        adults=2,
        children=0,
        rooms=1,
        currency="USD",
        constraints=[],
        property_types=[],
        occupancy_types=[],
    )

    patch = SearchIntentPatch(
        set_check_in="2024-08-08",
        set_check_out="2024-08-12",
    )

    check_in, check_out = _inherit_month_from_previous_state(
        previous_state=previous_state,
        patch=patch,
        normalized_check_in="2026-08-08",
        normalized_check_out="2026-08-12",
        user_text="change dates to 8-12",
    )

    assert check_in == "2026-08-08"
    assert check_out == "2026-08-12"


def test_followup_month_inheritance_is_temporarily_disabled_for_explicit_month_update():
    previous_state = SearchRequest(
        city="Baku",
        check_in="2026-04-20",
        check_out="2026-04-25",
        adults=2,
        children=0,
        rooms=1,
        currency="USD",
        constraints=[],
        property_types=[],
        occupancy_types=[],
    )

    patch = SearchIntentPatch(
        set_check_in="2024-08-08",
        set_check_out="2024-08-12",
    )

    check_in, check_out = _inherit_month_from_previous_state(
        previous_state=previous_state,
        patch=patch,
        normalized_check_in="2026-08-08",
        normalized_check_out="2026-08-12",
        user_text="change dates to 8-12 August",
    )

    assert check_in == "2026-08-08"
    assert check_out == "2026-08-12"