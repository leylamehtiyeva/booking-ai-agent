from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field as PydanticField, model_validator

from app.schemas.fields import Field
from app.schemas.filters import SearchFilters
from app.schemas.property_semantics import OccupancyType, PropertyType


class SearchRequest(BaseModel):
    """
    Canonical search request produced by intent router
    and consumed by all downstream services.
    """

    user_message: str

    city: str | None = None
    check_in: Optional[date] = None
    check_out: Optional[date] = None

    adults: int = 2
    children: int = 0
    rooms: int = 1

    currency: Optional[str] = "USD"
    budget_max: Optional[float] = None

    must_have_fields: List[Field] = PydanticField(default_factory=list)
    nice_to_have_fields: List[Field] = PydanticField(default_factory=list)
    forbidden_fields: List[Field] = PydanticField(default_factory=list)

    min_guest_rating: Optional[float] = None
    filters: SearchFilters | None = None

    property_types: list[PropertyType] | None = None
    occupancy_types: list[OccupancyType] | None = None

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.check_in and self.check_out and self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        return self