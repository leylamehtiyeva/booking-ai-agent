from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Tuple

from app.schemas.fields import Field
from app.schemas.listing import ListingRaw
from app.schemas.match import FieldMatch, MatchReport, Ternary
from app.schemas.query import SearchRequest
from app.schemas.match import Evidence, EvidenceSource, FieldMatch, MatchReport, Ternary


def _normalize_text(s: str) -> str:
    return " ".join(s.lower().strip().split())


def extract_facility_texts(facilities: List[Any]) -> List[str]:
    """
    facilities can be:
    - list[str]
    - list[dict] with keys like {"name": "..."}
    - mixed
    We normalize into list[str].
    """
    out: List[str] = []
    for x in facilities or []:
        if isinstance(x, str):
            out.append(_normalize_text(x))
        elif isinstance(x, dict):
            name = x.get("name")
            if isinstance(name, str) and name.strip():
                out.append(_normalize_text(name))
    return out


def collect_all_facilities(listing: ListingRaw) -> List[Tuple[str, str]]:
    """
    Collect facilities from listing + rooms with evidence path.
    Returns list of (facility_text, evidence_path).
    """
    results: List[Tuple[str, str]] = []

    # listing-level
    for t in extract_facility_texts(getattr(listing, "facilities", []) or []):
        results.append((t, "listing.facilities"))

    # rooms-level
    for i, room in enumerate(getattr(listing, "rooms", []) or []):
        room_fac = extract_facility_texts(getattr(room, "facilities", []) or [])
        for t in room_fac:
            results.append((t, f"rooms[{i}].facilities"))

    return results


@dataclass(frozen=True)
class KeywordRule:
    field: Field
    keywords: Tuple[str, ...]


def build_rules() -> List[KeywordRule]:
    """
    Minimal keyword rules for structured facilities matching.
    This is NOT user synonyms dictionary — these are Booking-style amenity strings.
    """
    return [
        KeywordRule(Field.KITCHEN, ("kitchen", "kitchenette", "cooking")),
        KeywordRule(Field.KETTLE, ("kettle", "electric kettle")),
        KeywordRule(Field.PRIVATE_BATHROOM, ("private bathroom",)),
        # 'bath' can mean bathtub OR just bathroom; keep it weak/uncertain unless you have a dedicated Field
        # KeywordRule(Field.BATH, ("bath", "bathtub")),
        KeywordRule(Field.WIFI, ("wifi", "wi-fi", "wireless internet")),
        KeywordRule(Field.AIR_CONDITIONING, ("air conditioning", "ac")),
    ]


def match_field_in_facilities(
    field: Field,
    facilities_with_paths: List[Tuple[str, str]],
    rules: List[KeywordRule],
) -> FieldMatch:
    """
    Match one Field using keyword rules on normalized facility texts.
    """
    rule = next((r for r in rules if r.field == field), None)
    if rule is None:
        # if we don't have a rule yet: cannot decide deterministically
        return FieldMatch(value=Ternary.UNCERTAIN, confidence=0.0, evidence=None)

    for fac_text, path in facilities_with_paths:
        for kw in rule.keywords:
            if kw in fac_text:
                return FieldMatch(
                    value=Ternary.YES,
                    confidence=0.95,
                    evidence=[
                        Evidence(
                            source=EvidenceSource.STRUCTURED,
                            path=path,
                            snippet=fac_text,
                        )
                    ],
                )


    # If we had rules but found nothing — say NO with moderate confidence.
    return FieldMatch(value=Ternary.NO, confidence=0.7, evidence=[])


def match_listing_structured(listing: ListingRaw, request: SearchRequest) -> MatchReport:
    """
    Deterministic matcher (no LLM).
    Only uses structured facilities + basic numeric fields.
    """
    facilities_with_paths = collect_all_facilities(listing)
    rules = build_rules()

    field_matches = {}
    for f in request.must_have_fields:
        field_matches[f] = match_field_in_facilities(f, facilities_with_paths, rules)

    # Optional: basic numeric checks (price/rating) could be added later.
    return MatchReport(listing_id=listing.id or listing.url or listing.name or "unknown", matches=field_matches)
