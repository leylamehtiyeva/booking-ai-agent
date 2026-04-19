from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExpectedConstraint(BaseModel):
    normalized_text: str
    priority: Literal["must", "nice", "forbidden"]
    category: str

    # New rich-fields for constraint-layer evaluation
    mapping_status: Literal["known", "unresolved"] | None = None
    mapped_fields: list[str] = Field(default_factory=list)
    evidence_strategy: Literal["structured", "textual", "geo", "none"] | None = None


class ConstraintEvalCase(BaseModel):
    case_id: str
    group: str
    user_message: str
    expected_constraints: list[ExpectedConstraint]