from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class OccupancyResult:
    requested_guests: int
    listing_capacity: int | None
    rooms_requested: int
    passed: bool
    reason: str


def _safe_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def extract_listing_max_occupancy(listing) -> int | None:
    """
    Prefer max(options[].persons) across available rooms.
    Fallback to max(room.persons).
    """
    rooms = getattr(listing, "rooms", None) or []
    option_caps: list[int] = []
    room_caps: list[int] = []

    for room in rooms:
        room_available = getattr(room, "available", True)

        options = getattr(room, "options", None) or []
        for opt in options:
            cap = _safe_int(getattr(opt, "persons", None))
            if cap is not None and room_available:
                option_caps.append(cap)

        room_cap = _safe_int(getattr(room, "persons", None))
        if room_cap is not None and room_available:
            room_caps.append(room_cap)

    if option_caps:
        return max(option_caps)

    if room_caps:
        return max(room_caps)

    return None


def evaluate_occupancy(listing, req) -> OccupancyResult:
    requested_guests = int((req.adults or 0) + (req.children or 0))
    rooms_requested = int(req.rooms or 1)

    capacity = extract_listing_max_occupancy(listing)

    if requested_guests <= 0:
        return OccupancyResult(
            requested_guests=0,
            listing_capacity=capacity,
            rooms_requested=rooms_requested,
            passed=True,
            reason="no occupancy requested",
        )

    if capacity is None:
        return OccupancyResult(
            requested_guests=requested_guests,
            listing_capacity=None,
            rooms_requested=rooms_requested,
            passed=True,
            reason="listing capacity unknown",
        )

    if capacity >= requested_guests:
        return OccupancyResult(
            requested_guests=requested_guests,
            listing_capacity=capacity,
            rooms_requested=rooms_requested,
            passed=True,
            reason=f"capacity {capacity} >= requested {requested_guests}",
        )

    return OccupancyResult(
        requested_guests=requested_guests,
        listing_capacity=capacity,
        rooms_requested=rooms_requested,
        passed=False,
        reason=f"capacity {capacity} < requested {requested_guests}",
    )