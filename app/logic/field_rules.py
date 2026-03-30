from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.schemas.fields import Field


from dataclasses import dataclass
from typing import Dict, Tuple

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
        negative_aliases=("no kitchen",),
    ),
    Field.PRIVATE_BATHROOM: FieldRule(
        aliases=("private bathroom",),
        preferred_path_prefixes=("rooms[", "listing.description"),
        negative_aliases=("shared bathroom", "shared toilet"),
    ),
    Field.WIFI: FieldRule(
        aliases=("wifi", "wi-fi", "free wifi", "wireless internet"),
        preferred_path_prefixes=("rooms[", "listing.facilities", "listing.description"),
        negative_aliases=("no wifi", "wifi not available", "internet not available"),
    ),
    Field.AIR_CONDITIONING: FieldRule(
        aliases=("air conditioning", "air-conditioned"),
        preferred_path_prefixes=("rooms[", "listing.facilities", "listing.description"),
        negative_aliases=("no air conditioning",),
    ),
    Field.WASHING_MACHINE: FieldRule(
        aliases=("washing machine",),
        preferred_path_prefixes=("rooms[", "listing.facilities", "listing.description"),
        negative_aliases=("no washing machine",),
    ),
    Field.OVEN: FieldRule(
        aliases=("oven",),
        preferred_path_prefixes=("rooms[", "listing.facilities", "listing.description"),
        negative_aliases=("no oven",),
    ),
    Field.MICROWAVE: FieldRule(
        aliases=("microwave",),
        preferred_path_prefixes=("rooms[", "listing.facilities", "listing.description"),
        negative_aliases=("no microwave",),
    ),
    Field.REFRIGERATOR: FieldRule(
        aliases=("refrigerator", "fridge"),
        preferred_path_prefixes=("rooms[", "listing.facilities", "listing.description"),
        negative_aliases=("no refrigerator", "no fridge"),
    ),
    Field.BALCONY: FieldRule(
        aliases=("balcony", "patio", "terrace"),
        preferred_path_prefixes=("rooms[", "highlights", "listing.description"),
        negative_aliases=("no balcony",),
    ),
    Field.KETTLE: FieldRule(
        aliases=("kettle", "electric kettle"),
        preferred_path_prefixes=("rooms[", "listing.facilities", "listing.description"),
        negative_aliases=("no kettle",),
    ),
    Field.COFFEE_MACHINE: FieldRule(
        aliases=("coffee machine", "coffee maker"),
        preferred_path_prefixes=("rooms[", "listing.facilities", "listing.description"),
        negative_aliases=("no coffee machine", "no coffee maker"),
    ),
    Field.FREE_CANCELLATION: FieldRule(
        aliases=("free cancellation",),
        preferred_path_prefixes=("rooms[", "policies", "highlights"),
        negative_aliases=("non-refundable", "no free cancellation"),
    ),
    Field.PET_FRIENDLY: FieldRule(
        aliases=("pets allowed", "pet friendly", "pets are allowed"),
        preferred_path_prefixes=("policies", "listing.description"),
        negative_aliases=("no pets", "pets not allowed", "pets are not allowed"),
    ),
    Field.PROPERTY_APARTMENT: FieldRule(
        aliases=("apartment", "private apartment in building"),
        preferred_path_prefixes=("listing.property_type", "listing.name", "rooms[", "listing.description"),
        negative_aliases=(),
    ),
}