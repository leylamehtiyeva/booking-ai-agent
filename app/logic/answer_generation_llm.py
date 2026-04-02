from __future__ import annotations

import asyncio
import json
import os
from typing import Any
import re
from app.logic.answer_generation import build_user_answer

import re


def _cleanup_llm_answer(text: str) -> str:
    text = (text or "").strip()

    # Normalize ugly raw-url markdown
    text = re.sub(
        r"\[(https?://[^\]]+)\]\((https?://[^)]+)\)",
        r"[View listing](\2)",
        text,
    )

    # Bare bullet url -> View listing
    text = re.sub(
        r"(^\s*[-*]\s+)(https?://\S+)$",
        r"\1[View listing](\2)",
        text,
        flags=re.MULTILINE,
    )

    # Remove bold markdown
    text = text.replace("**", "")

    # Normalize unsafe uncertainty phrasing
    unsafe_patterns = [
        (r"\bmight not allow pets\b", "pet policy is not confirmed"),
        (r"\bprobably does not allow pets\b", "pet policy is not confirmed"),
        (r"\blikely does not allow pets\b", "pet policy is not confirmed"),
        (r"\bit'?s uncertain if the second one does\b", "the pet policy for the second one is not confirmed"),
        (r"\bit'?s uncertain if .* allows pets\b", "the pet policy is not confirmed"),
    ]
    for pattern, repl in unsafe_patterns:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    # Tidy spacing
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text

def _gemini_client():
    try:
        from google.genai import Client
    except ImportError as e:
        raise ImportError("google-genai is not installed") from e

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY/GOOGLE_API_KEY")
    return Client(api_key=api_key)


def _genai_types():
    try:
        from google.genai import types as genai_types
    except ImportError as e:
        raise ImportError("google-genai is not installed") from e
    return genai_types


def _build_answer_system_prompt() -> str:
    return """
You are a booking search assistant.

You will receive a structured payload with:
- active_intent
- latest_user_query
- top_results
- clarification questions if needed

SOURCE OF TRUTH:
- active_intent
- top_results
- structured fields inside each result

ROLE OF latest_user_query:
- use it only to preserve user wording and conversational tone
- do NOT use it to add, remove, or reinterpret constraints
- if latest_user_query conflicts with active_intent, follow active_intent

YOUR GOAL:
Do not simply restate the payload.
Create a helpful user-facing answer that:
1. briefly summarizes the outcome,
2. compares the top options,
3. helps the user choose,
4. naturally invites refinement in the next turn.

CRITICAL RULE FOR UNCERTAINTY:
- If a constraint is uncertain, describe it as "not confirmed", "not explicitly stated", or "needs confirmation".
- Do NOT phrase uncertain constraints as negative.
- Do NOT say "might not", "probably not", "likely not", or anything similar unless the payload explicitly says the constraint failed.
- Only use negative wording when the payload says the constraint failed.

LINK RULE:
- Do NOT output raw URLs by themselves.
- Do NOT use the URL itself as the visible anchor text.
- If a result has a URL, format it exactly as:
  [View listing](URL)

STYLE RULES:
- Do NOT use bold formatting with ** **
- Keep the same structure for every listing
- Keep bullets short and parallel in style

TRUST RULES:
- Use ONLY the information in the payload
- Do NOT invent facts
- Do NOT claim something is confirmed if it is uncertain

FORMAT:
- Start with 1 short summary paragraph
- Then use numbered items: 1), 2), 3)
- For each option, use exactly this order:
  - one short line saying what makes it stand out
  - price and budget fit
  - key facts
  - trade-offs or uncertain points if any
  - [View listing](URL)
- End with one short sentence offering a concrete refinement

STYLE:
- concise
- trustworthy
- structured
- natural
- not salesy
- no JSON
""".strip()


async def generate_user_answer_with_llm(
    payload: dict[str, Any],
    *,
    model: str = "gemini-2.0-flash",
    use_fallback_on_error: bool = True,
) -> str:
    """
    Generate a user-facing booking answer from compact structured payload.

    Falls back to deterministic formatter if the model call fails.
    """
    system = _build_answer_system_prompt()
    user_prompt = (
    "Write the final user-facing answer based on this payload. "
    "Focus on comparison, decision support, and next-step refinement. "
    "Do not restate every field.\n\n"
    + json.dumps(payload, ensure_ascii=False, indent=2)
)

    def _call_sync() -> str:
        client = _gemini_client()
        genai_types = _genai_types()

        resp = client.models.generate_content(
            model=model,
            contents=[
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=user_prompt)],
                )
            ],
            config=genai_types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.3,
            ),
        )
        return (resp.text or "").strip()

    try:
        text = await asyncio.to_thread(_call_sync)
        text = _cleanup_llm_answer(text)
        if text:
            return text
        if use_fallback_on_error:
            return build_user_answer(payload)
        return ""
    except Exception:
        if use_fallback_on_error:
            return build_user_answer(payload)
        raise