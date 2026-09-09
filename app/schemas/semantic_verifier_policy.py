from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.config.llm import get_semantic_verifier_model


class SemanticVerifierPolicy(BaseModel):
    """
    Configuration for the Gemini semantic evidence verifier
    (app.logic.semantic_evidence_verification). Deliberately separate
    from FallbackPolicy - the old textual fallback and the new evidence
    pipeline are independent until the migration in the README's plan
    reaches the removal step.

    max_calls_per_hotel / max_calls_per_request are constructor-args
    only in Phase A - not read from any environment variable. They are
    conservative, unvalidated starting points meant to be revised once
    real shadow-mode call volume is observed, not derived from any
    production load data (none exists yet for this pipeline).
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    model: str = Field(default_factory=get_semantic_verifier_model)
    temperature: float = 0.0

    max_calls_per_hotel: int = 6
    max_calls_per_request: int = 20

    def normalized_max_calls_per_hotel(self) -> int:
        return max(0, self.max_calls_per_hotel)

    def normalized_max_calls_per_request(self) -> int:
        return max(0, self.max_calls_per_request)
