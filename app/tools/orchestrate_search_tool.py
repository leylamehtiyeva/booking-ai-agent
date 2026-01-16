from __future__ import annotations

import asyncio
import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from google.genai import Client
from google.genai import types as genai_types
from pydantic import ValidationError

from app.agents.intent_router_agent import IntentRoute
from app.logic.fallback_classifier import fallback_classify_field_async
from app.logic.matcher_structured import match_listing_structured
from app.schemas.fields import Field
from app.schemas.listing import ListingRaw
from app.schemas.match import Ternary
from app.schemas.query import SearchRequest


FIXTURES_PATH = Path("fixtures/listings_sample.json")


def _load_fixture_listings(path: Path = FIXTURES_PATH) -> List[ListingRaw]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [ListingRaw.model_validate(x) for x in data]


def _score_listing(req: SearchRequest, matches: dict[Field, Any]) -> Tuple[float, int, int, List[str]]:
    """MVP scoring.

    - must-have YES: +10
    - must-have UNCERTAIN: +3
    - must-have NO: -100
    - nice-to-have YES: +1
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


def _parse_iso_date(x: Any) -> Optional[date]:
    if x is None:
        return None
    if isinstance(x, date):
        return x
    if isinstance(x, str):
        try:
            return date.fromisoformat(x.strip())
        except ValueError:
            return None
    return None


def _covers_dates(lst: ListingRaw, check_in: date, check_out: date) -> bool:
    """MVP availability filter for fixtures (safety net).

    Apify typically returns listings already scoped to (city, dates),
    but mocks may contain mixed availability.
    """
    ad = getattr(lst, "available_dates", None)
    if ad is None:
        return True

    if isinstance(ad, dict):
        lst_in_raw = ad.get("check_in")
        lst_out_raw = ad.get("check_out")
    else:
        lst_in_raw = getattr(ad, "check_in", None)
        lst_out_raw = getattr(ad, "check_out", None)

    lst_in = _parse_iso_date(lst_in_raw)
    lst_out = _parse_iso_date(lst_out_raw)

    if lst_in is None or lst_out is None:
        return True

    return lst_in <= check_in and check_out <= lst_out


def _gemini_client() -> Client:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY/GOOGLE_API_KEY")
    return Client(api_key=api_key)


async def _repair_intent_with_llm(
    intent_raw: Dict[str, Any],
    errors: list[dict],
    model: str = "gemini-2.0-flash",
) -> Dict[str, Any]:
    """Ask LLM to repair intent to match IntentRoute exactly.

    No synonym dictionary is used here. The model must map meaning to Field.value.
    """
    allowed_values = [f.value for f in Field]

    system = (
        "You are a JSON repair assistant.\n"
        "Return ONLY a valid JSON object. No markdown. No code fences.\n"
        "Fix the JSON to match the target schema EXACTLY.\n"
        "must_have_fields and nice_to_have_fields MUST contain ONLY canonical keys from allowed_fields.\n"
        "If you cannot map an item to a canonical key, move it to unknown_requests.\n"
        "Do not invent new keys.\n"
    )

    payload = {
        "allowed_fields": allowed_values,
        "validation_errors": errors,
        "input_intent": intent_raw,
        "target_schema": {
            "city": "string|null",
            "check_in": "YYYY-MM-DD|null",
            "check_out": "YYYY-MM-DD|null",
            "must_have_fields": "list[canonical_key]",
            "nice_to_have_fields": "list[canonical_key]",
            "unknown_requests": "list[str]",
        },
    }

    def _call_sync() -> Dict[str, Any]:
        client = _gemini_client()
        resp = client.models.generate_content(
            model=model,
            contents=[
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=json.dumps(payload, ensure_ascii=False))],
                )
            ],
            config=genai_types.GenerateContentConfig(system_instruction=system),
        )
        text = (resp.text or "").strip()
        return json.loads(text)

    return await asyncio.to_thread(_call_sync)


def _salvage_only_enum_keys(intent_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Last resort: keep only enum-parsable items (by value or by name).

    Everything else is moved to unknown_requests.
    """
    out: Dict[str, Any] = {
        "city": intent_dict.get("city"),
        "check_in": intent_dict.get("check_in"),
        "check_out": intent_dict.get("check_out"),
        "must_have_fields": [],
        "nice_to_have_fields": [],
        "unknown_requests": list(intent_dict.get("unknown_requests") or []),
    }

    def parse_list(xs):
        ok = []
        for x in xs or []:
            if isinstance(x, Field):
                ok.append(x)
                continue
            if isinstance(x, str):
                s = x.strip()
                try:
                    ok.append(Field(s))
                    continue
                except Exception:
                    pass
                try:
                    ok.append(Field[s])
                    continue
                except Exception:
                    pass
                try:
                    ok.append(Field[s.upper()])
                    continue
                except Exception:
                    pass
                out["unknown_requests"].append(x)
            else:
                out["unknown_requests"].append(str(x))
        return ok

    out["must_have_fields"] = parse_list(intent_dict.get("must_have_fields"))
    out["nice_to_have_fields"] = parse_list(intent_dict.get("nice_to_have_fields"))
    return out


async def _validate_and_repair_intent(intent: Any, attempts: int = 2) -> Tuple[IntentRoute, List[str]]:
    """Validate intent as IntentRoute with up to N LLM repair attempts.

    Returns (intent_obj, dropped_requests).
    dropped_requests are items we could not map (ignored but later reported).
    """
    intent_work: Dict[str, Any] = intent if isinstance(intent, dict) else {}

    intent_obj: Optional[IntentRoute] = None
    for _ in range(max(0, attempts)):
        try:
            intent_obj = IntentRoute.model_validate(intent_work)
            break
        except ValidationError as e:
            try:
                intent_work = await _repair_intent_with_llm(intent_work, e.errors())
            except Exception:
                break

    if intent_obj is None:
        try:
            intent_obj = IntentRoute.model_validate(intent_work)
        except ValidationError:
            salvaged = _salvage_only_enum_keys(intent_work)
            intent_obj = IntentRoute.model_validate(salvaged)

    dropped: List[str] = []
    if getattr(intent_obj, "unknown_requests", None):
        dropped.extend(intent_obj.unknown_requests)

    return intent_obj, dropped


def _require_dates(intent_obj: IntentRoute) -> Tuple[Optional[date], Optional[date]]:
    return _parse_iso_date(getattr(intent_obj, "check_in", None)), _parse_iso_date(
        getattr(intent_obj, "check_out", None)
    )


def _build_request(user_text: str, intent_obj: IntentRoute, check_in: date, check_out: date) -> SearchRequest:
    return SearchRequest(
        user_message=user_text,
        city=intent_obj.city,
        check_in=check_in,
        check_out=check_out,
        adults=2,
        children=0,
        rooms=1,
        currency="USD",
        budget_max=None,
        must_have_fields=intent_obj.must_have_fields,
        nice_to_have_fields=intent_obj.nice_to_have_fields,
        forbidden_fields=[],
        min_guest_rating=None,
        property_types=None,
    )


def _rank_structured(req: SearchRequest, listings: List[ListingRaw]) -> List[Dict[str, Any]]:
    ranked: List[Dict[str, Any]] = []
    for lst in listings:
        report = match_listing_structured(lst, req)
        score, must_yes, must_total, why = _score_listing(req, report.matches)
        ranked.append(
            {
                "listing_name": lst.name,
                "listing_id": getattr(lst, "id", None),
                "matches": report.matches,
                "score": score,
                "must_have_matched": must_yes,
                "must_have_total": must_total,
                "why": why,
                "listing": lst,
            }
        )
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked


async def _apply_fallback_topk(req: SearchRequest, ranked: List[Dict[str, Any]], fallback_top_k: int) -> None:
    for item in ranked[: max(0, fallback_top_k)]:
        has_uncertain = any(
            item["matches"].get(f) is not None and item["matches"][f].value == Ternary.UNCERTAIN
            for f in (req.must_have_fields or [])
        )
        if not has_uncertain:
            continue

        for f in (req.must_have_fields or []):
            fm = item["matches"].get(f)
            if fm is not None and fm.value == Ternary.UNCERTAIN:
                fm2 = await fallback_classify_field_async(item["listing"], f)
                item["matches"][f] = fm2

        score, must_yes, must_total, why = _score_listing(req, item["matches"])
        item["score"] = score
        item["must_have_matched"] = must_yes
        item["must_have_total"] = must_total
        item["why"] = why

    ranked.sort(key=lambda x: x["score"], reverse=True)


def _format_results(req: SearchRequest, ranked: List[Dict[str, Any]], top_n: int, dropped_requests: List[str]) -> Dict[str, Any]:
    results_out = []
    for r in ranked[: max(0, top_n)]:
        results_out.append(
            {
                "title": r["listing_name"],
                "score": r["score"],
                "must": f"{r['must_have_matched']}/{r['must_have_total']}",
                "why": r["why"],
            }
        )

    not_found_fields = set()
    for r in ranked[: max(0, top_n)]:
        for f in (req.must_have_fields or []):
            fm = r["matches"].get(f)
            if fm is not None and fm.value == Ternary.NO:
                not_found_fields.add(f.value)

    notes = []
    if dropped_requests:
        notes.append(f"Could not map (ignored): {sorted(set(dropped_requests))}")
    if not_found_fields:
        notes.append(f"Not found in top results: {sorted(not_found_fields)}")

    summary = (
        f"city={req.city}, check_in={req.check_in}, check_out={req.check_out}, "
        f"must_have={[f.value for f in (req.must_have_fields or [])]}, "
        f"nice_to_have={[f.value for f in (req.nice_to_have_fields or [])]}"
    )
    if notes:
        summary += " | " + " | ".join(notes)

    return {
        "need_clarification": False,
        "summary": summary,
        "results": results_out,
    }


async def orchestrate_search(
    user_text: str,
    intent: Dict[str, Any],
    top_n: int = 5,
    fallback_top_k: int = 5,
) -> Dict[str, Any]:
    """High-level search orchestration tool (fixtures MVP)."""
    intent_obj, dropped_requests = await _validate_and_repair_intent(intent, attempts=2)

    check_in, check_out = _require_dates(intent_obj)
    if check_in is None or check_out is None:
        return {
            "need_clarification": True,
            "questions": ["Какие даты заезда и выезда? (формат YYYY-MM-DD)"],
        }

    req = _build_request(user_text=user_text, intent_obj=intent_obj, check_in=check_in, check_out=check_out)

    listings = _load_fixture_listings()
    listings = [lst for lst in listings if _covers_dates(lst, req.check_in, req.check_out)]

    if not listings:
        return {
            "need_clarification": True,
            "questions": ["На выбранные даты в текущих примерах ничего не найдено. Попробуешь другие даты?"],
        }

    ranked = _rank_structured(req, listings)
    await _apply_fallback_topk(req, ranked, fallback_top_k=fallback_top_k)

    return _format_results(req, ranked, top_n=top_n, dropped_requests=dropped_requests)
