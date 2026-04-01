from __future__ import annotations

from typing import Any


def _first_reason(constraints: list[dict[str, Any]] | None) -> str | None:
    for item in constraints or []:
        reason = item.get("reason")
        if reason:
            return str(reason)
    return None


def _format_top_result(result: dict[str, Any], rank: int) -> str:
    title = result.get("title") or "Unknown option"
    url = result.get("url")
    matched_must = result.get("matched_must") or "0/0"

    matched_constraints = result.get("matched_constraints") or []
    uncertain_constraints = result.get("uncertain_constraints") or []
    key_facts = result.get("key_facts") or {}
    best_reasons = result.get("best_reasons") or []

    lines = [f"{rank}. {title}"]

    must_total = 0
    if "/" in matched_must:
        left, right = matched_must.split("/", 1)
        try:
            must_total = int(right)
        except ValueError:
            must_total = 0

    if must_total > 0:
        lines.append(f"Matched required criteria: {matched_must}.")

    summary_bits = []

    if key_facts.get("property_type"):
        summary_bits.append(f"type: {key_facts['property_type']}")
    if key_facts.get("bedrooms") is not None:
        summary_bits.append(f"{key_facts['bedrooms']} bedrooms")
    if key_facts.get("area_sqm") is not None:
        summary_bits.append(f"{key_facts['area_sqm']} sqm")
    if key_facts.get("listing_price_total") is not None and key_facts.get("listing_currency"):
        summary_bits.append(
            f"total price: {key_facts['listing_price_total']} {key_facts['listing_currency']}"
        )

    if summary_bits:
        lines.append("Key facts: " + ", ".join(summary_bits) + ".")

    if best_reasons:
        lines.append("Why it matches: " + "; ".join(best_reasons) + ".")

    if uncertain_constraints:
        uncertain_names = [
            x.get("name") for x in uncertain_constraints if x.get("name")
        ]
        if uncertain_names:
            lines.append(
                "Uncertain points: " + ", ".join(uncertain_names) + "."
            )

    if url:
        lines.append(f"Link: {url}")

    return "\n".join(lines)


def build_user_answer(payload: dict[str, Any]) -> str:
    """
    Deterministic user-facing formatter for LLM-ready payload.

    This is intentionally simple and stable.
    Later it can be replaced or wrapped by an LLM-based rewriter.
    """
    if payload.get("need_clarification"):
        questions = payload.get("questions") or []
        if not questions:
            return "I need one more detail to continue."
        if len(questions) == 1:
            return questions[0]
        return "I need a few more details:\n- " + "\n- ".join(questions)

    request_summary = payload.get("request_summary") or {}
    city = request_summary.get("city")
    check_in = request_summary.get("check_in")
    check_out = request_summary.get("check_out")
    top_results = payload.get("top_results") or []

    if not top_results:
        if city and check_in and check_out:
            return (
                f"I couldn’t find suitable options in {city} "
                f"for {check_in} to {check_out}."
            )
        return "I couldn’t find suitable options."

    intro_bits = []
    if city:
        intro_bits.append(f"in {city}")
    if check_in and check_out:
        intro_bits.append(f"for {check_in} to {check_out}")

    intro_suffix = ""
    if intro_bits:
        intro_suffix = " " + " ".join(intro_bits)

    lines = [f"I found {len(top_results)} option(s){intro_suffix}."]
    lines.append("Here are the best matches:")

    for idx, result in enumerate(top_results, start=1):
        lines.append("")
        lines.append(_format_top_result(result, idx))

    return "\n".join(lines)