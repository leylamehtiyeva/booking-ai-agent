from __future__ import annotations
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, List, Optional, Tuple
from app.schemas.filters import SearchFilters
from app.schemas.listing import ListingRaw
from app.schemas.match import Evidence, EvidenceSource, Ternary
from app.schemas.filters import PriceConstraint, SearchFilters


_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}


@dataclass(frozen=True)
class NumericMatchResult:
    attribute: str
    value: Ternary
    actual_value: float | int | None
    evidence: List[Evidence]
    why: str


def _normalize_text(s: str) -> str:
    return " ".join(s.lower().strip().split())


def _word_to_number(token: str) -> Optional[int]:
    token = token.lower().strip()
    if token.isdigit():
        return int(token)
    return _NUMBER_WORDS.get(token)


def _collect_text_candidates(listing: ListingRaw) -> List[Tuple[str, str]]:
    """
    Собираем все разумные текстовые места, где могут встретиться
    bedroom count / area.

    Возвращаем список:
    [
        (normalized_text, "evidence.path"),
        ...
    ]
    """
    out: List[Tuple[str, str]] = []

    def add(path: str, value: Any) -> None:
        if isinstance(value, str) and value.strip():
            out.append((_normalize_text(value), path))
        elif isinstance(value, list):
            parts = [str(x).strip() for x in value if str(x).strip()]
            if parts:
                out.append((_normalize_text(" ".join(parts)), path))

    add("listing.name", getattr(listing, "name", None))
    add("listing.description", getattr(listing, "description", None))
    add("listing.bedTypes", getattr(listing, "bedTypes", None))

    for i, room in enumerate(getattr(listing, "rooms", []) or []):
        add(f"rooms[{i}].name", getattr(room, "name", None))
        add(f"rooms[{i}].roomType", getattr(room, "roomType", None))
        add(f"rooms[{i}].bedTypes", getattr(room, "bedTypes", None))
        add(f"rooms[{i}].facilities", getattr(room, "facilities", None))

    return out


def _parse_bedroom_mentions(text: str) -> List[int]:
    found: List[int] = []

    # "3-bedroom", "3 bedrooms", "three bedroom", "three-bedroom"
    for m in re.finditer(
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)[-\s]+bedroom(?:s)?\b",
        text,
    ):
        n = _word_to_number(m.group(1))
        if n is not None:
            found.append(n)

    # "3 bed apartment" — более слабый сигнал, но можно поддержать
    for m in re.finditer(
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+bed\b",
        text,
    ):
        n = _word_to_number(m.group(1))
        if n is not None:
            found.append(n)

    # studio = 0 bedrooms
    if re.search(r"\bstudio\b", text):
        found.append(0)

    return found


def extract_bedroom_count(listing: ListingRaw) -> tuple[int | None, List[Evidence]]:
    """
    Пытаемся детерминированно извлечь количество bedrooms.

    Эвристика:
    - ищем bedroom mentions в listing.name / description / rooms[].*
    - если найдено несколько кандидатов:
        1) предпочитаем rooms[*] и listing.name
        2) среди них берём максимальное значение
    """
    candidates: List[tuple[int, Evidence, int]] = []

    for text, path in _collect_text_candidates(listing):
        values = _parse_bedroom_mentions(text)
        for val in values:
            priority = 1 if path.startswith("rooms[") or path == "listing.name" else 0
            candidates.append(
                (
                    val,
                    Evidence(
                        source=EvidenceSource.STRUCTURED,
                        path=path,
                        snippet=text,
                    ),
                    priority,
                )
            )

    if not candidates:
        return None, []

    candidates.sort(key=lambda x: (x[2], x[0]), reverse=True)
    best_value, best_evidence, _ = candidates[0]
    return best_value, [best_evidence]


_AREA_PATTERNS = [
    (
        re.compile(
            r"\b(\d+(?:[\.,]\d+)?)\s*(?:sqm|sq\.?\s*m|m²|m2|square meters?|square metres?)\b"
        ),
        1.0,
    ),
    (
        re.compile(
            r"\b(\d+(?:[\.,]\d+)?)\s*(?:sq\.?\s*ft|ft²|ft2|square feet|feet²)\b"
        ),
        0.092903,
    ),
]


def _parse_area_mentions(text: str) -> List[float]:
    out: List[float] = []

    for pattern, multiplier in _AREA_PATTERNS:
        for m in pattern.finditer(text):
            raw = m.group(1).replace(",", ".")
            try:
                area = round(float(raw) * multiplier, 2)
                out.append(area)
            except ValueError:
                continue

    return out


def extract_area_sqm(listing: ListingRaw) -> tuple[float | None, List[Evidence]]:
    """
    Пытаемся извлечь площадь в sqm.

    Поддерживаем:
    - 80 sqm
    - 80 m² / m2
    - 2196 sq ft / feet²  -> конвертируем в sqm
    """
    candidates: List[tuple[float, Evidence, int]] = []

    for text, path in _collect_text_candidates(listing):
        values = _parse_area_mentions(text)
        for val in values:
            priority = 1 if path.startswith("rooms[") or path == "listing.name" else 0
            candidates.append(
                (
                    val,
                    Evidence(
                        source=EvidenceSource.STRUCTURED,
                        path=path,
                        snippet=text,
                    ),
                    priority,
                )
            )

    if not candidates:
        return None, []

    candidates.sort(key=lambda x: (x[2], x[0]), reverse=True)
    best_value, best_evidence, _ = candidates[0]
    return best_value, [best_evidence]


def match_bedrooms_filters(
    bedroom_count: int | None,
    filters: SearchFilters | None,
    evidence: List[Evidence] | None = None,
) -> NumericMatchResult | None:
    if filters is None or (filters.bedrooms_min is None and filters.bedrooms_max is None):
        return None

    evidence = evidence or []

    if bedroom_count is None:
        return NumericMatchResult(
            attribute="bedrooms",
            value=Ternary.UNCERTAIN,
            actual_value=None,
            evidence=evidence,
            why="BEDROOMS: could not extract bedroom count",
        )

    if filters.bedrooms_min is not None and bedroom_count < filters.bedrooms_min:
        return NumericMatchResult(
            attribute="bedrooms",
            value=Ternary.NO,
            actual_value=bedroom_count,
            evidence=evidence,
            why=f"BEDROOMS: {bedroom_count} < required min {filters.bedrooms_min}",
        )

    if filters.bedrooms_max is not None and bedroom_count > filters.bedrooms_max:
        return NumericMatchResult(
            attribute="bedrooms",
            value=Ternary.NO,
            actual_value=bedroom_count,
            evidence=evidence,
            why=f"BEDROOMS: {bedroom_count} > allowed max {filters.bedrooms_max}",
        )

    if filters.bedrooms_min is not None and filters.bedrooms_max is not None:
        why = f"BEDROOMS: {bedroom_count} within [{filters.bedrooms_min}, {filters.bedrooms_max}]"
    elif filters.bedrooms_min is not None:
        why = f"BEDROOMS: {bedroom_count} >= required {filters.bedrooms_min}"
    else:
        why = f"BEDROOMS: {bedroom_count} <= allowed {filters.bedrooms_max}"

    return NumericMatchResult(
        attribute="bedrooms",
        value=Ternary.YES,
        actual_value=bedroom_count,
        evidence=evidence,
        why=why,
    )


def match_area_filters(
    area_sqm: float | None,
    filters: SearchFilters | None,
    evidence: List[Evidence] | None = None,
) -> NumericMatchResult | None:
    if filters is None or (filters.area_sqm_min is None and filters.area_sqm_max is None):
        return None

    evidence = evidence or []

    if area_sqm is None:
        return NumericMatchResult(
            attribute="area_sqm",
            value=Ternary.UNCERTAIN,
            actual_value=None,
            evidence=evidence,
            why="AREA: could not extract area",
        )

    pretty = int(area_sqm) if float(area_sqm).is_integer() else round(area_sqm, 1)

    if filters.area_sqm_min is not None and area_sqm < filters.area_sqm_min:
        return NumericMatchResult(
            attribute="area_sqm",
            value=Ternary.NO,
            actual_value=area_sqm,
            evidence=evidence,
            why=f"AREA: {pretty} sqm < required min {filters.area_sqm_min}",
        )

    if filters.area_sqm_max is not None and area_sqm > filters.area_sqm_max:
        return NumericMatchResult(
            attribute="area_sqm",
            value=Ternary.NO,
            actual_value=area_sqm,
            evidence=evidence,
            why=f"AREA: {pretty} sqm > allowed max {filters.area_sqm_max}",
        )

    if filters.area_sqm_min is not None and filters.area_sqm_max is not None:
        why = f"AREA: {pretty} sqm within [{filters.area_sqm_min}, {filters.area_sqm_max}]"
    elif filters.area_sqm_min is not None:
        why = f"AREA: {pretty} sqm >= required {filters.area_sqm_min}"
    else:
        why = f"AREA: {pretty} sqm <= allowed {filters.area_sqm_max}"

    return NumericMatchResult(
        attribute="area_sqm",
        value=Ternary.YES,
        actual_value=area_sqm,
        evidence=evidence,
        why=why,
    )
    
def _normalize_currency(value: str | None) -> str | None:
    if not value:
        return None

    s = value.strip().upper()

    mapping = {
        "US$": "USD",
        "$": "USD",
        "USD": "USD",
        "AZN": "AZN",
        "MANAT": "AZN",
        "MANATS": "AZN",
        "EUR": "EUR",
        "€": "EUR",
        "GBP": "GBP",
        "£": "GBP",
    }
    return mapping.get(s, s)


def _night_count(check_in: date | None, check_out: date | None) -> int | None:
    if check_in is None or check_out is None:
        return None
    delta = (check_out - check_in).days
    if delta <= 0:
        return None
    return delta


def extract_total_price(listing: ListingRaw) -> tuple[float | None, str | None, List[Evidence]]:
    """
    Booking JSON in your current flow appears to expose total stay price at top-level:
    listing.price + listing.currency.
    """
    price = getattr(listing, "price", None)
    currency = _normalize_currency(getattr(listing, "currency", None))

    if price is not None:
        evidence = [
            Evidence(
                source=EvidenceSource.STRUCTURED,
                path="listing.price",
                snippet=f"price={price}, currency={currency}",
            )
        ]
        return float(price), currency, evidence

    # fallback: first room option price
    rooms = getattr(listing, "rooms", []) or []
    for i, room in enumerate(rooms):
        options = getattr(room, "options", []) or []
        for j, opt in enumerate(options):
            opt_price = getattr(opt, "price", None)
            opt_currency = _normalize_currency(getattr(opt, "currency", None))
            if opt_price is not None:
                evidence = [
                    Evidence(
                        source=EvidenceSource.STRUCTURED,
                        path=f"rooms[{i}].options[{j}].price",
                        snippet=f"price={opt_price}, currency={opt_currency}",
                    )
                ]
                return float(opt_price), opt_currency, evidence

    return None, None, []


def match_price_filters(
    total_price: float | None,
    listing_currency: str | None,
    filters: SearchFilters | None,
    *,
    check_in: date | None,
    check_out: date | None,
    evidence: List[Evidence] | None = None,
) -> NumericMatchResult | None:
    if filters is None or filters.price is None:
        return None

    price_filter = filters.price
    evidence = evidence or []

    if total_price is None:
        return NumericMatchResult(
            attribute="price_total",
            value=Ternary.UNCERTAIN,
            actual_value=None,
            evidence=evidence,
            why="PRICE: could not extract total listing price",
        )

    listing_currency_norm = _normalize_currency(listing_currency)
    request_currency_norm = _normalize_currency(price_filter.currency)

    if (
        request_currency_norm is not None
        and listing_currency_norm is not None
        and request_currency_norm != listing_currency_norm
    ):
        return NumericMatchResult(
            attribute="price_total",
            value=Ternary.UNCERTAIN,
            actual_value=total_price,
            evidence=evidence,
            why=(
                f"PRICE: currency mismatch listing={listing_currency_norm}, "
                f"request={request_currency_norm}"
            ),
        )

    required_min_total = price_filter.min_amount
    required_max_total = price_filter.max_amount

    if price_filter.scope == "per_night":
        nights = _night_count(check_in, check_out)
        if nights is None:
            return NumericMatchResult(
                attribute="price_total",
                value=Ternary.UNCERTAIN,
                actual_value=total_price,
                evidence=evidence,
                why="PRICE: could not derive night count for per-night budget",
            )

        if required_min_total is not None:
            required_min_total = required_min_total * nights
        if required_max_total is not None:
            required_max_total = required_max_total * nights

    elif price_filter.scope in ("total_stay", None):
        pass

    else:
        return NumericMatchResult(
            attribute="price_total",
            value=Ternary.UNCERTAIN,
            actual_value=total_price,
            evidence=evidence,
            why=f"PRICE: unsupported scope {price_filter.scope}",
        )

    pretty_total = round(total_price, 2)

    if required_min_total is not None and total_price < required_min_total:
        return NumericMatchResult(
            attribute="price_total",
            value=Ternary.NO,
            actual_value=total_price,
            evidence=evidence,
            why=f"PRICE: {pretty_total} < required min total {round(required_min_total, 2)}",
        )

    if required_max_total is not None and total_price > required_max_total:
        return NumericMatchResult(
            attribute="price_total",
            value=Ternary.NO,
            actual_value=total_price,
            evidence=evidence,
            why=f"PRICE: {pretty_total} > allowed max total {round(required_max_total, 2)}",
        )

    if required_min_total is not None and required_max_total is not None:
        why = (
            f"PRICE: {pretty_total} within total range "
            f"[{round(required_min_total, 2)}, {round(required_max_total, 2)}]"
        )
    elif required_min_total is not None:
        why = f"PRICE: {pretty_total} >= required total {round(required_min_total, 2)}"
    else:
        why = f"PRICE: {pretty_total} <= allowed total {round(required_max_total, 2)}"

    return NumericMatchResult(
        attribute="price_total",
        value=Ternary.YES,
        actual_value=total_price,
        evidence=evidence,
        why=why,
    )   
   
    
def evaluate_numeric_filters(
    listing: ListingRaw,
    filters: SearchFilters | None,
    *,
    check_in: date | None = None,
    check_out: date | None = None,
) -> List[NumericMatchResult]:
    """
    Единая точка входа для numeric extraction + matching.
    """
    bedroom_count, bedroom_evidence = extract_bedroom_count(listing)
    area_sqm, area_evidence = extract_area_sqm(listing)
    total_price, listing_currency, price_evidence = extract_total_price(listing)

    results: List[NumericMatchResult] = []

    br = match_bedrooms_filters(
        bedroom_count=bedroom_count,
        filters=filters,
        evidence=bedroom_evidence,
    )
    if br is not None:
        results.append(br)

    ar = match_area_filters(
        area_sqm=area_sqm,
        filters=filters,
        evidence=area_evidence,
    )
    if ar is not None:
        results.append(ar)

    pr = match_price_filters(
        total_price=total_price,
        listing_currency=listing_currency,
        filters=filters,
        check_in=check_in,
        check_out=check_out,
        evidence=price_evidence,
    )
    if pr is not None:
        results.append(pr)

    return results


