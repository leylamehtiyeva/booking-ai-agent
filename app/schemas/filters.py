from __future__ import annotations

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    """
    Typed structured constraints extracted from the user query.

    These are NOT boolean amenity fields and therefore should not be stored
    in must_have_fields / nice_to_have_fields.
    """
    bedrooms_min: int | None = None
    bedrooms_max: int | None = None
    area_sqm_min: float | None = None
    area_sqm_max: float | None = None