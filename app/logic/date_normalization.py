from __future__ import annotations

import re
from datetime import date, timedelta

from app.logic.request_resolution import parse_iso_date


YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
CHINESE_YEAR_PATTERN = re.compile(r"(19|20)\d{2}\s*年")


def user_explicitly_mentioned_year(user_text: str) -> bool:
    return bool(
        YEAR_PATTERN.search(user_text) or CHINESE_YEAR_PATTERN.search(user_text)
    )




def normalize_intent_dates(intent, user_text: str, *, today: date | None = None):
    """
    Normalize parsed intent dates for the first user turn.

    Rules:
    - if user did NOT explicitly mention a year, force parsed dates to current year
    - if check_in exists and check_out is missing but nights exists -> compute check_out
    - if only check_in exists -> default to 1 night
    """
    today = today or date.today()
    explicit_year = user_explicitly_mentioned_year(user_text)

    check_in = parse_iso_date(getattr(intent, "check_in", None))
    check_out = parse_iso_date(getattr(intent, "check_out", None))
    nights = getattr(intent, "nights", None)

    if not explicit_year:
        if check_in is not None:
            check_in = check_in.replace(year=today.year)
        if check_out is not None:
            check_out = check_out.replace(year=today.year)

    if check_in and check_out is None and nights is not None and nights > 0:
        check_out = check_in + timedelta(days=nights)

    if check_in and check_out is None and nights is None:
        check_out = check_in + timedelta(days=1)

    data = intent.model_dump()
    data["check_in"] = check_in.isoformat() if check_in else None
    data["check_out"] = check_out.isoformat() if check_out else None
    return intent.__class__(**data)


def normalize_patch_dates(
    *,
    set_check_in: str | None,
    set_check_out: str | None,
    set_nights: int | None,
    user_text: str,
    today: date | None = None,
) -> tuple[str | None, str | None]:
    """
    Normalize parsed dates for follow-up patch updates.

    Rules:
    - if user did NOT explicitly mention a year, force parsed dates to current year
    - if check_in exists and check_out is missing but nights exists -> compute check_out
    - do NOT decide month here; month inheritance from previous state is handled
      in intent_update.py
    """
    today = today or date.today()
    explicit_year = user_explicitly_mentioned_year(user_text)

    check_in = parse_iso_date(set_check_in)
    check_out = parse_iso_date(set_check_out)

    if not explicit_year:
        if check_in is not None:
            check_in = check_in.replace(year=today.year)
        if check_out is not None:
            check_out = check_out.replace(year=today.year)

    if check_in and check_out is None and set_nights is not None and set_nights > 0:
        check_out = check_in + timedelta(days=set_nights)

    return (
        check_in.isoformat() if check_in else None,
        check_out.isoformat() if check_out else None,
    )