from __future__ import annotations

import asyncio
import json

from app.logic.intent_router import build_search_request_adk_async


async def main():
    queries = [
        "I want an apartment in Baku from 2026-04-08 to 2026-04-15 with private bathroom, kitchen, at least 2 bedrooms and at least 80 sqm",
        "Apartment in Baku with private bathroom and less than 50 sqm",
        "Apartment in Baku with kitchen between 70 and 90 sqm",
    ]

    for i, q in enumerate(queries, start=1):
        print(f"\n\n######## TEST {i} ########")
        print("USER QUERY:", q)

        req = await build_search_request_adk_async(q)

        print("\nFINAL REQUEST JSON:")
        print(json.dumps(req.model_dump(mode="json", exclude_none=True), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())