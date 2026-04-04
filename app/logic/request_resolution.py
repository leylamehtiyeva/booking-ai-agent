from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.agents.intent_router_agent import IntentRoute


@dataclass
class ResolvedSearchContext:
    city: str | None
    check_in: date | None
    check_out: date | None
    questions: list[str]

    @property
    def need_clarification(self) -> bool:
        return len(self.questions) > 0


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def resolve_required_search_context(intent: IntentRoute) -> ResolvedSearchContext:
    questions: list[str] = []

    city = (intent.city or "").strip() or None
    check_in = parse_iso_date(intent.check_in)
    check_out = parse_iso_date(intent.check_out)
    nights = intent.nights

    if not city:
        questions.append("Which city should I search in?")

    if check_in and check_out:
        if check_out <= check_in:
            questions.append("Please уточни даты: check-out must be later than check-in.")
    elif check_in and nights is not None:
        if nights <= 0:
            questions.append("Please specify a valid number of nights.")
        else:
            check_out = check_in + timedelta(days=nights)
    elif check_in and not check_out:
        check_out = check_in + timedelta(days=1)
    elif check_out and not check_in:
        questions.append("Please specify the check-in date.")
    else:
        questions.append(
            "Please specify the travel dates. You can give one date or a period, for example: 2026-04-20 for 6 nights."
        )

    return ResolvedSearchContext(
        city=city,
        check_in=check_in,
        check_out=check_out,
        questions=questions,
    )