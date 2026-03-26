from __future__ import annotations

from typing import Protocol, List
from app.schemas.query import SearchRequest
from app.schemas.listing import ListingRaw


class CandidateRetriever(Protocol):
    async def get_candidates(self, req: SearchRequest, max_items: int) -> List[ListingRaw]:
        ...
        
    