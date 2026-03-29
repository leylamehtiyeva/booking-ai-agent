from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.schemas.fields import Field


@dataclass(frozen=True)
class FieldRule:
    aliases: Tuple[str, ...]
    preferred_path_prefixes: Tuple[str, ...] = ()
    negative_aliases: Tuple[str, ...] = ()


FIELD_RULES: Dict[Field, FieldRule] = {
    Field.KITCHEN: FieldRule(
        aliases=("kitchen", "private kitchen", "kitchenette", "shared kitchen"),
        preferred_path_prefixes=("rooms[", "listing.facilities", "listing.description"),
    ),
    Field.PRIVATE_BATHROOM: FieldRule(
        aliases=("private bathroom",),
        preferred_path_prefixes=("rooms[", "listing.description"),
    ),
    Field.WIFI: FieldRule(
        aliases=("wifi", "wi-fi", "free wifi", "wireless internet"),
        preferred_path_prefixes=("rooms[", "listing.facilities", "listing.description"),
    ),
    Field.AIR_CONDITIONING: FieldRule(
        aliases=("air conditioning", "air-conditioned"),
        preferred_path_prefixes=("rooms[", "listing.facilities", "listing.description"),
    ),
    Field.WASHING_MACHINE: FieldRule(
        aliases=("washing machine",),
        preferred_path_prefixes=("rooms[", "listing.facilities", "listing.description"),
    ),
    Field.OVEN: FieldRule(
        aliases=("oven",),
        preferred_path_prefixes=("rooms[", "listing.facilities", "listing.description"),
    ),
    Field.MICROWAVE: FieldRule(
        aliases=("microwave",),
        preferred_path_prefixes=("rooms[", "listing.facilities", "listing.description"),
    ),
    Field.REFRIGERATOR: FieldRule(
        aliases=("refrigerator", "fridge"),
        preferred_path_prefixes=("rooms[", "listing.facilities", "listing.description"),
    ),
    Field.BALCONY: FieldRule(
        aliases=("balcony", "patio", "terrace"),
        preferred_path_prefixes=("rooms[", "highlights", "listing.description"),
    ),
    Field.KETTLE: FieldRule(
        aliases=("kettle", "electric kettle"),
        preferred_path_prefixes=("rooms[", "listing.facilities", "listing.description"),
    ),
    Field.COFFEE_MACHINE: FieldRule(
        aliases=("coffee machine", "coffee maker"),
        preferred_path_prefixes=("rooms[", "listing.facilities", "listing.description"),
    ),
    Field.FREE_CANCELLATION: FieldRule(
        aliases=("free cancellation",),
        preferred_path_prefixes=("rooms[", "policies", "highlights"),
    ),
    Field.PET_FRIENDLY: FieldRule(
        aliases=("pets allowed", "pet friendly", "pets are allowed"),
        preferred_path_prefixes=("policies", "listing.description"),
    ),
    Field.PROPERTY_APARTMENT: FieldRule(
        aliases=("apartment", "private apartment in building"),
        preferred_path_prefixes=("listing.property_type", "listing.name", "rooms[", "listing.description"),
    ),
}