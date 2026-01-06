# app/agents/fallback_classifier_agent.py
from __future__ import annotations

import os
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini


FALLBACK_CLASSIFIER_INSTRUCTION = """
You are a strict classifier.

Task:
Given:
- a FIELD (one of the allowed enum values)
- LISTING_TEXT (description + amenities text)

Return ONLY valid JSON (no markdown fences) with this schema:
{
  "value": "YES" | "NO" | "UNCERTAIN",
  "confidence": number,   // 0.0 to 1.0
  "snippet": string       // short quoted fragment from LISTING_TEXT that supports the decision, or "" if none
}

Rules:
- Use YES only if the text clearly implies the FIELD is present.
- Use NO only if the text clearly implies the FIELD is absent.
- Otherwise use UNCERTAIN.
- confidence must reflect certainty.
- snippet must be copied from LISTING_TEXT (verbatim) when possible.
- Output MUST start with { and end with }.
"""


def build_fallback_classifier_agent(
    model_name: str = "models/gemini-2.0-flash",
) -> Agent:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY or GOOGLE_API_KEY")

    llm = Gemini(
        model=model_name,
        api_key=api_key,
    )

    return Agent(
        name="fallback_classifier",
        model=llm,
        instruction=FALLBACK_CLASSIFIER_INSTRUCTION,
    )
