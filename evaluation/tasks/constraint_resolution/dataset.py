from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


Decision = Literal["YES", "NO", "UNCERTAIN"]


class EvidenceItem(BaseModel):
    source: str
    text: str
    path: str | None = None


class ConstraintItem(BaseModel):
    raw_text: str
    normalized_text: str
    priority: str
    category: str
    mapping_status: str
    evidence_strategy: str
    mapped_fields: list[str] = Field(default_factory=list)
    structured_value: Decision | None = None


class ConstraintResolutionEvalCase(BaseModel):
    case_id: str
    case_type: str
    difficulty: str
    constraint: ConstraintItem
    listing_evidence: list[EvidenceItem]
    expected_decision: Decision
    expected_explicit_negative: bool = False
    explanation: str = ""


def load_constraint_resolution_dataset(path: str | Path) -> list[ConstraintResolutionEvalCase]:
    cases: list[ConstraintResolutionEvalCase] = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            raw_case = json.loads(line)
            cases.append(ConstraintResolutionEvalCase.model_validate(raw_case))

    return cases