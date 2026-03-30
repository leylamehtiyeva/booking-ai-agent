from __future__ import annotations

import hashlib

from app.schemas.listing import ListingRaw


def build_result_id(listing: ListingRaw) -> str:
    listing_id = getattr(listing, "id", None)
    if listing_id:
        return str(listing_id)

    url = getattr(listing, "url", None)
    if url:
        return "url_" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]

    name = getattr(listing, "name", "") or ""
    description = getattr(listing, "description", "") or ""
    base = f"{name}|{description[:200]}"
    return "gen_" + hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]