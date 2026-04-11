from __future__ import annotations

from typing import Any


def _format_bullets(items: list[str] | None, prefix: str = "- ") -> list[str]:
    out: list[str] = []
    for item in items or []:
        if item:
            out.append(f"{prefix}{item}")
    return out

def _format_constraint_rows(items: list[dict[str, Any]] | None) -> list[str]:
    out: list[str] = []

    for item in items or []:
        label = item.get("label") or "Requested detail"
        reason = item.get("reason")

        if reason and reason != label:
            out.append(f"- {label} — {reason}")
        else:
            out.append(f"- {label}")

    return out


def _format_top_result(result: dict[str, Any], rank: int) -> str:
    title = result.get("title") or "Unknown option"
    url = result.get("url")
    price_summary = result.get("price_summary")
    budget_summary = result.get("budget_summary")
    key_facts_summary = result.get("key_facts_summary")

    explanation = result.get("answer_explanation") or {}
    status_text = explanation.get("status_text")
    decision_summary = explanation.get("decision_summary")
    confirmed = explanation.get("confirmed") or []
    needs_confirmation = explanation.get("needs_confirmation") or []
    not_satisfied = explanation.get("not_satisfied") or []
    tradeoff_summary = explanation.get("tradeoff_summary")
    strengths_summary = explanation.get("strengths_summary")

    lines = [f"{rank}. {title}"]

    if status_text:
        lines.append(f"Status: {status_text}")

    if decision_summary:
        lines.append(f"Summary: {decision_summary}")

    if confirmed:
        lines.append("Confirmed:")
        lines.extend(_format_constraint_rows(confirmed))

    if needs_confirmation:
        lines.append("Needs confirmation:")
        lines.extend(_format_constraint_rows(needs_confirmation))
        
    if strengths_summary:
        lines.append(strengths_summary)

    if not_satisfied:
        lines.append("Not satisfied:")
        lines.extend(_format_constraint_rows(not_satisfied))

    if tradeoff_summary:
        lines.append(tradeoff_summary)

    if price_summary:
        lines.append(f"Price: {price_summary}")

    if budget_summary:
        lines.append(f"Budget: {budget_summary}")

    if key_facts_summary:
        lines.append(f"Key facts: {key_facts_summary}")

    unresolved_constraint_points = (
        result.get("unresolved_constraint_points")
        or result.get("unknown_request_points")
        or []
    )
    if unresolved_constraint_points:
        lines.append("Other requested details:")
        lines.extend(_format_bullets(unresolved_constraint_points))

    if url:
        lines.append(f"Link: {url}")

    return "\n".join(lines)


def _build_intro(payload: dict[str, Any]) -> str:
    active_intent = payload.get("active_intent") or {}
    city = active_intent.get("city")
    check_in = active_intent.get("check_in")
    check_out = active_intent.get("check_out")
    results_count = payload.get("results_count") or 0
    shown_count = len(payload.get("top_results") or [])

    parts: list[str] = []
    if city:
        parts.append(f"in {city}")
    if check_in and check_out:
        parts.append(f"for {check_in} to {check_out}")

    tail = ""
    if parts:
        tail = " " + " ".join(parts)

    if results_count > shown_count > 0:
        return (
            f"I found {results_count} relevant option(s){tail}. "
            f"Here are the top {shown_count} matches."
        )
    return f"I found {shown_count} relevant option(s){tail}."


def _build_refinement_hint(payload: dict[str, Any]) -> str:
    active_intent = payload.get("active_intent") or {}
    filters = active_intent.get("filters") or {}
    must_have_fields = active_intent.get("must_have_fields") or []
    constraints = active_intent.get("constraints") or []

    suggestions: list[str] = []

    if constraints:
        suggestions.append("focus on listings with more fully confirmed requested constraints")
    elif must_have_fields:
        suggestions.append("keep only listings with fully confirmed amenities")
    if filters.get("price"):
        suggestions.append("tighten or relax the budget")
    suggestions.append("narrow by location")
    suggestions.append("change bedroom / bathroom / area requirements")

    unique: list[str] = []
    for s in suggestions:
        if s not in unique:
            unique.append(s)

    return "I can also refine this further — for example, I can " + ", ".join(unique[:3]) + "."


def build_user_answer(payload: dict[str, Any]) -> str:
    """
    Deterministic user-facing formatter.

    This formatter should remain stable, explicit, and safe.
    It uses active_intent as source of truth and latest_user_query only implicitly.
    """
    if payload.get("need_clarification"):
        questions = payload.get("questions") or []
        if not questions:
            return "I need one more detail to continue."
        if len(questions) == 1:
            return questions[0]
        return "I need a few more details:\n- " + "\n- ".join(questions)

    top_results = payload.get("top_results") or []
    active_intent = payload.get("active_intent") or {}
    city = active_intent.get("city")
    check_in = active_intent.get("check_in")
    check_out = active_intent.get("check_out")

    if not top_results:
        if city and check_in and check_out:
            return (
                f"I couldn’t find suitable options in {city} "
                f"for {check_in} to {check_out}. "
                "I can help relax the budget, area, or amenity constraints."
            )
        return "I couldn’t find suitable options. I can help relax or clarify the constraints."

    lines = [_build_intro(payload)]
    lines.append("")

    for idx, result in enumerate(top_results, start=1):
        lines.append(_format_top_result(result, idx))
        if idx < len(top_results):
            lines.append("")

    lines.append("")
    lines.append(_build_refinement_hint(payload))

    return "\n".join(lines)