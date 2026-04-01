from __future__ import annotations

import asyncio
import json
import os

from google.genai import Client
from google.genai import types as genai_types

from app.logic.answer_generation import build_user_answer


def _gemini_client() -> Client:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY/GOOGLE_API_KEY")
    return Client(api_key=api_key)


def _build_answer_system_prompt() -> str:
    return """
You are a booking search assistant.

You will receive a structured payload with:
- request_summary
- top_results
- clarification questions if needed

Your job:
- explain what was found
- explain why the option(s) are good matches
- if there are multiple options, compare them briefly
- if there are uncertain points, mention them clearly and honestly
- if clarification is needed, ask the question naturally

Rules:
- Use ONLY the information in the payload
- Do NOT invent facts
- Do NOT claim something is confirmed if it is uncertain
- Keep the answer concise, helpful, and natural
- If there is 1 result, summarize it clearly
- If there are multiple results, summarize differences briefly
- If need_clarification=true, ask only the clarification question(s)
- Do not output JSON
""".strip()


async def generate_user_answer_with_llm(
    payload: dict,
    *,
    model: str = "gemini-2.0-flash",
    use_fallback_on_error: bool = True,
) -> str:
    """
    Generate a user-facing booking answer from compact structured payload.

    Falls back to deterministic formatter if the model call fails.
    """
    system = _build_answer_system_prompt()
    user_prompt = json.dumps(payload, ensure_ascii=False, indent=2)

    def _call_sync() -> str:
        client = _gemini_client()
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
        if text:
            return text
        if use_fallback_on_error:
            return build_user_answer(payload)
        return ""
    except Exception:
        if use_fallback_on_error:
            return build_user_answer(payload)
        raise