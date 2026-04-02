from __future__ import annotations

import asyncio
import json

from app.logic.intent_router import route_intent_adk_async
from app.logic.listing_signals import collect_listing_signals
from app.logic.unknown_field_evidence_search import search_unknown_must_have_evidence
from app.logic.unknown_request_utils import get_unknown_must_have_requests
from app.retrieval.fixtures import FixturesRetriever
from app.schemas.query import SearchRequest


USER_TEXT = (
    "I want an apartment in Baku from 2026-04-08 to 2026-04-15 "
    "with satellite TV and ironing facilities."
)


def _signal_preview(signals, limit: int = 12) -> list[dict]:
    preview = []
    for s in signals[:limit]:
        if hasattr(s, "model_dump"):
            preview.append(s.model_dump(mode="json"))
        else:
            preview.append(
                {
                    "path": getattr(s, "path", None),
                    "text": getattr(s, "text", None),
                }
            )
    return preview


async def main():
    print("\n=== USER TEXT ===")
    print(USER_TEXT)

    intent = await route_intent_adk_async(USER_TEXT)
    intent_dict = intent.model_dump(mode="json", exclude_none=True)

    print("\n=== INTENT ===")
    print(json.dumps(intent_dict, ensure_ascii=False, indent=2))

    unknown_requests = get_unknown_must_have_requests(intent_dict)

    print("\n=== UNKNOWN REQUESTS ===")
    print(json.dumps(unknown_requests, ensure_ascii=False, indent=2))

    retriever = FixturesRetriever()
    req = SearchRequest(
        user_message=USER_TEXT,
        city=intent_dict.get("city"),
        check_in=intent_dict.get("check_in"),
        check_out=intent_dict.get("check_out"),
        must_have_fields=intent_dict.get("must_have_fields", []),
        nice_to_have_fields=intent_dict.get("nice_to_have_fields", []),
        filters=intent_dict.get("filters", {}),
        property_types=intent_dict.get("property_types", []),
        occupancy_types=intent_dict.get("occupancy_types", []),
        unknown_requests=intent_dict.get("unknown_requests", []),
    )

    listings = await retriever.get_candidates(req, max_items=5)

    if not listings:
        print("No fixture listings found.")
        return

    print("\n=== CANDIDATES ===")
    for i, listing in enumerate(listings, start=1):
        print(f"{i}. {getattr(listing, 'name', 'Unknown listing')}")

    for req_text in unknown_requests:
        print(f"\n==============================")
        print(f"=== UNKNOWN MUST-HAVE: {req_text} ===")
        print(f"==============================")

        for i, listing in enumerate(listings, start=1):
            title = getattr(listing, "name", "Unknown listing")
            signals = collect_listing_signals(listing)

            print(f"\n--- LISTING {i}: {title} ---")
            print("Sample signals:")
            print(json.dumps(_signal_preview(signals), ensure_ascii=False, indent=2))

            result = await search_unknown_must_have_evidence(
                query_text=req_text,
                listing_signals=signals,
            )

            print("Result:")
            print(result.model_dump_json(indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())