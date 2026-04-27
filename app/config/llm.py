from __future__ import annotations

import os


DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


def get_gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip().strip('"')


def get_gemini_model_for_adk() -> str:
    model = get_gemini_model()
    return model if model.startswith("models/") else f"models/{model}"