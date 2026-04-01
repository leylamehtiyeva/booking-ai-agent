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

    lines = [f"{rank}. {title}"]

    lines.append(f"Matched required criteria: {matched_must}.")

    reason = _first_reason(matched_constraints)
    if reason:
        lines.append(f"Main match: {reason}")

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