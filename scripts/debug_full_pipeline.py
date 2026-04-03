from __future__ import annotations

import asyncio
import json

from app.logic.intent_router import route_intent_adk_async
from app.tools.orchestrate_search_tool import orchestrate_search

USER_TEXT = (
"I want an apartment in Baku from 2026-04-08 to 2026-04-15 with satellite TV and ironing facilities."
)


async def main():
    print("\n=== USER TEXT ===")
    print(USER_TEXT)

    intent = await route_intent_adk_async(USER_TEXT)

    if hasattr(intent, "model_dump"):
        intent_dict = intent.model_dump()
    else:
        intent_dict = intent

    print("\n=== INTENT ===")
    print(json.dumps(intent_dict, ensure_ascii=False, indent=2, default=str))

    result = await orchestrate_search(
        user_text=USER_TEXT,
        intent=intent_dict,
        source="fixtures",
        max_items=5,        # держим маленьким
        top_n=5,
        fallback_top_k=0,   # чтобы не было лишних LLM-вызовов на fallback
    )

    print("\n=== FINAL RESULT ===")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())