from datetime import date

from app.agents.intent_router_agent import IntentRoute
from app.logic.date_normalization import normalize_intent_dates
from app.schemas.constraints import (
    ConstraintCategory,
    ConstraintMappingStatus,
    ConstraintPriority,
    EvidenceStrategy,
    UserConstraint,
)


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


def test_first_turn_unresolved_constraints_clear_guessed_dates_even_when_unknown_requests_is_empty():
    intent = IntentRoute(
        city="Baku",
        check_in="2024-08-08",
        check_out="2024-08-16",
        constraints=[
            UserConstraint(
                raw_text="quiet neighborhood",
                normalized_text="quiet neighborhood",
                priority=ConstraintPriority.MUST,
                category=ConstraintCategory.LOCATION,
                mapping_status=ConstraintMappingStatus.UNRESOLVED,
                mapped_fields=[],
                evidence_strategy=EvidenceStrategy.TEXTUAL,
            )
        ],
        unknown_requests=[],
    )

    normalized = normalize_intent_dates(
        intent,
        "I want something in Baku maybe 8 to 16 august in a quiet neighborhood",
        today=date(2026, 4, 5),
    )

    assert normalized.check_in is None
    assert normalized.check_out is None