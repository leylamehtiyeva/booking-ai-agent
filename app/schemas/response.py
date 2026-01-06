from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from app.schemas.fields import Field
from app.schemas.match import FieldMatch
from app.schemas.listing import ListingRaw


class RankedListing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listing: ListingRaw
    score: float
    must_have_matched: int
    must_have_total: int
    matches: dict[Field, FieldMatch]
    why: List[str]  # короткие причины для пользователя


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_summary: str
    results: List[RankedListing]
