from __future__ import annotations

from typing import List, Literal

from app.schemas.listing import ListingRaw
from app.schemas.query import SearchRequest

from app.retrieval.fixtures import FixturesRetriever
from app.retrieval.apify import ApifyRetriever


Source = Literal["fixtures", "apify"]


async def get_candidates(req: SearchRequest, max_items: int, source: Source = "fixtures") -> List[ListingRaw]:
    if source == "fixtures":
        return await FixturesRetriever().get_candidates(req, max_items=max_items)
    if source == "apify":
        return await ApifyRetriever().get_candidates(req, max_items=max_items)
    raise ValueError(f"Unknown source={source}")
