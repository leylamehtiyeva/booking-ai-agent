from __future__ import annotations

import os
import json
from typing import Any, Dict

from google.adk.agents import Agent, SequentialAgent
from google.adk.models.google_llm import Gemini

from app.tools.orchestrate_search_tool import orchestrate_search


def _gemini_llm(model_name: str) -> Gemini:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Missing GOOGLE_API_KEY")
    return Gemini(model=model_name, api_key=api_key)


def build_orchestrator_agent(model_name: str = "models/gemini-2.0-flash") -> SequentialAgent:
    llm = _gemini_llm(model_name)

    # Step 1: Intent routing строго в JSON (без tools, без function_call)
    intent_step_instruction = """
    You extract a structured intent for a property search.

    Return ONLY a valid JSON object (no markdown, no ```).

    The user may write in ANY language. Your output must be canonical and consistent.

    JSON schema (return exactly these keys):
    {
    "city": string|null,
    "check_in": string|null,   // YYYY-MM-DD
    "check_out": string|null,  // YYYY-MM-DD
    "must_have_fields": [string],
    "nice_to_have_fields": [string],
    "unknown_requests": [string]
    }

    Rules:
    - If dates are not provided, set check_in/check_out to null.
    - If you cannot confidently map a request to supported keys, put the original phrase into unknown_requests.
    - Output JSON only.
    """



    intent_step = Agent(
        name="intent_router_step",
        model=llm,
        instruction=intent_step_instruction,
        tools=[],  # ВАЖНО: чтобы не было function_call на этом шаге
    )

    # Step 2: Вызов orchestrate_search + финальный текст
    search_step_instruction = """
You are step 2 of the pipeline.

You have:
- the original user request (the first user message in the session);
- the JSON intent from the previous step.

Follow these rules strictly:

1) Parse the previous step JSON into an object named intent.
2) If intent.check_in is null OR intent.check_out is null:
   - Ask ONE question to get the missing dates (YYYY-MM-DD), and STOP.
   - Do NOT call orchestrate_search.
3) If intent.unknown_requests is not empty:
   - Ask ONE clarifying question about the unknown items, and STOP.
   - Do NOT call orchestrate_search.
4) Otherwise call:
   orchestrate_search(user_text=<original user request>, intent=intent, top_n=5, fallback_top_k=5)
5) If the tool returns need_clarification=True:
   - Ask the returned questions and STOP.
6) Otherwise respond in Russian with:
   - a short summary
   - top results as a list (title + why)
Always return TEXT.
"""


    search_step = Agent(
        name="search_step",
        model=llm,
        instruction=search_step_instruction,
        tools=[orchestrate_search],
    )

    return SequentialAgent(
        name="orchestrator",
        sub_agents=[intent_step, search_step],
    )
