from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


ConversationRouteType = Literal[
    "search_update",
    "listing_question",
    "new_search",
    "other",
]


class ConversationRouteDecision(BaseModel):
    route: ConversationRouteType
    reason: Optional[str] = None