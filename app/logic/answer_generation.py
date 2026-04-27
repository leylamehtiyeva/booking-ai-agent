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


def _format_constraint_resolution_points(
    result: dict[str, Any],
) -> list[str]:
    """
    Convert canonical constraint_resolution_results into short, user-facing lines.

    Priority:
    1. explicit matches from constraint_resolution_results
    2. fallback to unresolved_constraint_points if already provided upstream

    This keeps answer_generation aligned with canonical payloads.
    """
    points: list[str] = []

    for item in result.get("constraint_resolution_results") or []:
        if not isinstance(item, dict):
            continue

        label = item.get("normalized_text")
        if not label:
            continue

        reason = item.get("reason")
        if isinstance(reason, str) and reason:
            points.append(f"{label} — {reason}")
        else:
            points.append(str(label))

    if points:
        seen: set[str] = set()
        unique: list[str] = []
        for p in points:
            if p not in seen:
                seen.add(p)
                unique.append(p)
        return unique[:4]

    fallback_points = result.get("unresolved_constraint_points") or []
    out: list[str] = []
    for item in fallback_points:
        if item:
            text = str(item)
            if text not in out:
                out.append(text)
    return out[:4]


def _format_top_result(result: dict[str, Any], rank: int) -> str:
    title = result.get("title") or "Unknown option"
    url = result.get("url")
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

    standout_reason = result.get("standout_reason")
    if standout_reason:
        lines.append(f"Standout: {standout_reason}")

    price_summary = result.get("price_summary")
    if price_summary:
        lines.append(f"Price: {price_summary}")

    if budget_summary:
        lines.append(f"Budget: {budget_summary}")

    if key_facts_summary:
        lines.append(f"Key facts: {key_facts_summary}")

    why_match = result.get("why_match") or []
    if why_match:
        lines.append("Why it matches:")
        lines.extend(_format_bullets(why_match))

    tradeoffs = result.get("tradeoffs") or []
    if tradeoffs:
        lines.append("Trade-offs:")
        lines.extend(_format_bullets(tradeoffs))

    uncertain_points = result.get("uncertain_points") or []
    if uncertain_points:
        lines.append("Uncertain points:")
        lines.extend(_format_bullets(uncertain_points))

    resolved_requested_details = _format_constraint_resolution_points(result)
    if resolved_requested_details:
        lines.append("Other requested details:")
        lines.extend(_format_bullets(resolved_requested_details))

    unresolved_constraint_points = result.get("unresolved_constraint_points") or []
    if unresolved_constraint_points:
        lines.append("Still needs confirmation:")
        lines.extend(_format_bullets(unresolved_constraint_points))

    ranking_reasons = result.get("ranking_reasons") or []
    if ranking_reasons:
        lines.append("Ranking signals:")
        lines.extend(_format_bullets([str(x) for x in ranking_reasons[:3]]))

    if url:
        lines.append(f"Link: {url}")

    return "\n".join(lines)


def _get_request_context(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Prefer active_intent as canonical runtime state.
    Fall back to request_summary for tests / normalized payloads that do not
    include active_intent.
    """
    return (payload.get("active_intent") or payload.get("request_summary") or {})


def _build_intro(payload: dict[str, Any]) -> str:
    request_ctx = _get_request_context(payload)
    city = request_ctx.get("city")
    check_in = request_ctx.get("check_in")
    check_out = request_ctx.get("check_out")
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
    request_ctx = _get_request_context(payload)
    filters = request_ctx.get("filters") or {}
    constraints = request_ctx.get("constraints") or []

    suggestions: list[str] = []

    if constraints:
        suggestions.append("focus on listings with more fully confirmed requested constraints")
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
    It prefers active_intent as the source of truth, but can fall back to
    request_summary for normalized/test payloads.
    """
    if payload.get("need_clarification"):
        questions = payload.get("questions") or []
        debug_notes = payload.get("debug_notes") or []

        base_text = ""
        if not questions:
            base_text = "I need one more detail to continue."
        elif len(questions) == 1:
            base_text = questions[0]
        else:
            base_text = "I need a few more details:\n- " + "\n- ".join(questions)

        if debug_notes:
            return base_text + "\n\nDebug notes:\n- " + "\n- ".join(debug_notes)

        return base_text

    top_results = payload.get("top_results") or []
    request_ctx = _get_request_context(payload)
    city = request_ctx.get("city")
    check_in = request_ctx.get("check_in")
    check_out = request_ctx.get("check_out")

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