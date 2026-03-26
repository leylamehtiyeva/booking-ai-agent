from __future__ import annotations

import json
from pathlib import Path
from typing import List

from app.schemas.listing import ListingRaw
from app.schemas.query import SearchRequest


FIXTURES_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "listings_sample.json"



class FixturesRetriever:
    def __init__(self, path: Path = FIXTURES_PATH):
        self.path = path

    async def get_candidates(self, req: SearchRequest, max_items: int) -> List[ListingRaw]:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        listings = [ListingRaw.model_validate(x) for x in data]
        return listings[:max_items]
