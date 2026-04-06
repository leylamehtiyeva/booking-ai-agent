from datetime import date

from app.agents.intent_router_agent import IntentRoute
from app.logic.date_normalization import normalize_intent_dates


def test_normalize_intent_dates_sets_current_year_when_user_did_not_specify_year():
    intent = IntentRoute(
        city="Baku",
        check_in="2024-04-08",
        check_out="2024-04-15",
    )

    normalized = normalize_intent_dates(
        intent,
        "apartment in Baku 8 april to 15 april",
        today=date(2026, 4, 5),
    )

    assert normalized.check_in == "2026-04-08"
    assert normalized.check_out == "2026-04-15"


def test_normalize_intent_dates_keeps_explicit_year():
    intent = IntentRoute(
        city="Baku",
        check_in="2024-04-08",
        check_out="2024-04-15",
    )

    normalized = normalize_intent_dates(
        intent,
        "apartment in Baku from 2024-04-08 to 2024-04-15",
        today=date(2026, 4, 5),
    )

    assert normalized.check_in == "2024-04-08"
    assert normalized.check_out == "2024-04-15"


def test_normalize_intent_dates_computes_check_out_from_nights():
    intent = IntentRoute(
        city="Baku",
        check_in="2024-04-20",
        check_out=None,
        nights=6,
    )

    normalized = normalize_intent_dates(
        intent,
        "Baku 20 april for 6 nights",
        today=date(2026, 4, 5),
    )

    assert normalized.check_in == "2026-04-20"
    assert normalized.check_out == "2026-04-26"


def test_first_turn_unknown_requests_clears_guessed_dates():
    intent = IntentRoute(
        city="Baku",
        check_in="2024-08-08",
        check_out="2024-08-16",
        unknown_requests=["с 8 по 16 ое?"],
    )

    normalized = normalize_intent_dates(
        intent,
        "в баку с 8 по 16 ое?",
        today=date(2026, 4, 5),
    )

    assert normalized.check_in is None
    assert normalized.check_out is None