from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple
from app.logic.intent_router import build_search_request_adk_async

from app.schemas.query import SearchRequest
from app.schemas.fields import Field
from app.schemas.listing import ListingRaw
from app.schemas.match import Ternary
from app.schemas.response import SearchResponse, RankedListing

from app.logic.matcher_structured import match_listing_structured
from app.logic.fallback_classifier import fallback_classify_field_async


FIXTURES_PATH = Path("fixtures/listings_sample.json")


def _load_fixture_listings(path: Path = FIXTURES_PATH) -> List[ListingRaw]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [ListingRaw.model_validate(x) for x in data]


def _score_listing(req: SearchRequest, matches: dict[Field, object]) -> Tuple[float, int, int, List[str]]:
    """
    Очень простой скоринг для MVP:
    - must-have YES: +10
    - must-have UNCERTAIN: +3
    - must-have NO: -100 (почти выкидываем)
    - nice-to-have YES: +1
    + причины why (коротко)
    """
    score = 0.0
    why: List[str] = []

    must_total = len(req.must_have_fields or [])
    must_yes = 0

    for f in (req.must_have_fields or []):
        fm = matches[f]
        if fm.value == Ternary.YES:
            score += 10
            must_yes += 1
            if fm.evidence:
                why.append(f"{f.name}: {fm.evidence[0].snippet}")
            else:
                why.append(f"{f.name}: matched")
        elif fm.value == Ternary.UNCERTAIN:
            score += 3
            why.append(f"{f.name}: maybe (needs check)")
        else:
            score -= 100
            why.append(f"{f.name}: not found")

    for f in (req.nice_to_have_fields or []):
        fm = matches.get(f)
        if fm and fm.value == Ternary.YES:
            score += 1
            if fm.evidence:
                why.append(f"+ {f.name}: {fm.evidence[0].snippet}")

    return score, must_yes, must_total, why


async def run_orchestrator(
    user_text: str,
    top_n: int = 5,
    fallback_top_k: int = 5,
    listings_source: str = "fixtures",  # "fixtures" | "apify" (apify позже)
) -> SearchResponse:
    # 1) Intent routing (LLM через ADK) -> SearchRequest
    req = await build_search_request_adk_async(user_text)

    # 2) Fetch candidates
    if listings_source == "fixtures":
        listings = _load_fixture_listings()
    else:
        raise NotImplementedError("Apify source will be enabled after Jan 23")

    # 3) Structured match для всех
    reports = []
    for lst in listings:
        report = match_listing_structured(lst, req)
        reports.append((lst, report))

    # 4) Быстрый ранк до fallback (чтобы выбрать top-K)
    pre_ranked: List[RankedListing] = []
    for lst, report in reports:
        score, must_yes, must_total, why = _score_listing(req, report.matches)
        pre_ranked.append(
            RankedListing(
                listing=lst,
                score=score,
                must_have_matched=must_yes,
                must_have_total=must_total,
                matches=report.matches,
                why=why,
            )
        )
    pre_ranked.sort(key=lambda x: x.score, reverse=True)

    # 5) Fallback только для top-K и только для must-have где UNCERTAIN
    for item in pre_ranked[:fallback_top_k]:
        for f in (req.must_have_fields or []):
            if item.matches[f].value == Ternary.UNCERTAIN:
                fm2 = await fallback_classify_field_async(item.listing, f)
                item.matches[f] = fm2

        # пересчёт score/why после fallback
        score, must_yes, must_total, why = _score_listing(req, item.matches)
        item.score = score
        item.must_have_matched = must_yes
        item.must_have_total = must_total
        item.why = why

    # 6) Финальный ранк
    pre_ranked.sort(key=lambda x: x.score, reverse=True)

    summary = f"city={req.city}, must_have={[f.name for f in (req.must_have_fields or [])]}"
    return SearchResponse(
        request_summary=summary,
        results=pre_ranked[:top_n],
    )
