from app.logic.intent_update import _inherit_month_from_previous_state
from app.schemas.intent_patch import SearchIntentPatch
from app.schemas.query import SearchRequest


def test_followup_inherits_month_from_previous_state():
    previous_state = SearchRequest(
        user_message="apartment in Baku from 20 april to 25 april",
        city="Baku",
        check_in="2026-04-20",
        check_out="2026-04-25",
        adults=2,
        children=0,
        rooms=1,
        currency="USD",
        must_have_fields=[],
        nice_to_have_fields=[],
        forbidden_fields=[],
        property_types=[],
        occupancy_types=[],
    )

    patch = SearchIntentPatch(
        set_check_in="2024-08-08",
        set_check_out="2024-08-16",
    )

    check_in, check_out = _inherit_month_from_previous_state(
        previous_state=previous_state,
        patch=patch,
        normalized_check_in="2026-08-08",
        normalized_check_out="2026-08-16",
    )

    assert check_in == "2026-04-08"
    assert check_out == "2026-04-16"