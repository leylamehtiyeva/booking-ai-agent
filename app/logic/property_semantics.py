from __future__ import annotations

from dataclasses import dataclass
from typing import List
from app.schemas.listing import ListingRaw
from app.schemas.property_semantics import OccupancyType, PropertyType
from app.schemas.match import Ternary, Evidence, EvidenceSource


@dataclass
class SemanticMatchResult:
    attribute: str
    value: Ternary
    actual_value: str | None
    evidence: List[Evidence]
    why: str


def _texts_for_listing(listing: ListingRaw) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []

    name = getattr(listing, "name", None)
    if name:
        out.append(("listing.name", name))

    description = getattr(listing, "description", None)
    if description:
        out.append(("listing.description", description))

    listing_type = getattr(listing, "type", None)
    if listing_type:
        out.append(("listing.type", str(listing_type)))

    rooms = getattr(listing, "rooms", []) or []
    for i, room in enumerate(rooms):
        room_type = getattr(room, "roomType", None)
        if room_type:
            out.append((f"rooms[{i}].roomType", room_type))

        facilities = getattr(room, "facilities", []) or []
        for j, facility in enumerate(facilities):
            if facility:
                out.append((f"rooms[{i}].facilities[{j}]", str(facility)))

    return out


def detect_property_type(listing: ListingRaw) -> tuple[PropertyType | None, list[Evidence]]:
    texts = _texts_for_listing(listing)

    rules = [
        (PropertyType.APARTHOTEL, ["aparthotel"]),
        (PropertyType.HOSTEL, ["hostel"]),
        (PropertyType.HOTEL, ["hotel"]),
        (PropertyType.APARTMENT, ["apartment", "apartments", "flat", "studio"]),
        (PropertyType.HOUSE, ["house", "villa", "home"]),
        (PropertyType.GUESTHOUSE, ["guesthouse", "guest house"]),
    ]

    for path, text in texts:
        low = text.lower()
        for ptype, patterns in rules:
            for pattern in patterns:
                if pattern in low:
                    return (
                        ptype,
                        [
                            Evidence(
                                source=EvidenceSource.STRUCTURED,
                                path=path,
                                snippet=pattern,
                            )
                        ],
                    )

    return None, []


def detect_occupancy_type(listing: ListingRaw) -> tuple[OccupancyType | None, list[Evidence]]:
    texts = _texts_for_listing(listing)

    rules = [
        (OccupancyType.ENTIRE_PLACE, ["entire apartment", "entire place", "entire studio", "entire home"]),
        (OccupancyType.PRIVATE_ROOM, ["private room"]),
        (OccupancyType.SHARED_ROOM, ["shared room", "bed in dorm", "dormitory room", "shared dorm"]),
        (OccupancyType.HOTEL_ROOM, ["hotel room", "double room", "twin room"]),
    ]

    for path, text in texts:
        low = text.lower()
        for otype, patterns in rules:
            for pattern in patterns:
                if pattern in low:
                    return (
                        otype,
                        [
                            Evidence(
                                source=EvidenceSource.STRUCTURED,
                                path=path,
                                snippet=pattern,
                            )
                        ],
                    )

    return None, []


def match_property_types(
    listing: ListingRaw,
    requested: list[PropertyType] | None,
) -> SemanticMatchResult | None:
    if not requested:
        return None

    detected, evidence = detect_property_type(listing)
    if detected is None:
        return SemanticMatchResult(
            attribute="property_type",
            value=Ternary.UNCERTAIN,
            actual_value=None,
            evidence=evidence,
            why="PROPERTY_TYPE: could not determine property type",
        )

    if detected not in requested:
        return SemanticMatchResult(
            attribute="property_type",
            value=Ternary.NO,
            actual_value=detected.value,
            evidence=evidence,
            why=f"PROPERTY_TYPE: detected {detected.value}, expected one of {[x.value for x in requested]}",
        )

    return SemanticMatchResult(
        attribute="property_type",
        value=Ternary.YES,
        actual_value=detected.value,
        evidence=evidence,
        why=f"PROPERTY_TYPE: matched {detected.value}",
    )


def match_occupancy_types(
    listing: ListingRaw,
    requested: list[OccupancyType] | None,
) -> SemanticMatchResult | None:
    if not requested:
        return None

    detected, evidence = detect_occupancy_type(listing)
    if detected is None:
        return SemanticMatchResult(
            attribute="occupancy_type",
            value=Ternary.UNCERTAIN,
            actual_value=None,
            evidence=evidence,
            why="OCCUPANCY_TYPE: could not determine occupancy type",
        )

    if detected not in requested:
        return SemanticMatchResult(
            attribute="occupancy_type",
            value=Ternary.NO,
            actual_value=detected.value,
            evidence=evidence,
            why=f"OCCUPANCY_TYPE: detected {detected.value}, expected one of {[x.value for x in requested]}",
        )

    return SemanticMatchResult(
        attribute="occupancy_type",
        value=Ternary.YES,
        actual_value=detected.value,
        evidence=evidence,
        why=f"OCCUPANCY_TYPE: matched {detected.value}",
    )