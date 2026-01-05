# app/schemas/match.py
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.fields import Field as CanonicalField


class Ternary(str, Enum):
    YES = "YES"
    NO = "NO"
    UNCERTAIN = "UNCERTAIN"


class EvidenceSource(str, Enum):
    STRUCTURED = "structured"
    LLM = "llm"
    LLM_FALLBACK = "llm_fallback"



class Evidence(BaseModel):
    """
    Evidence = минимальная единица объяснения.
    Мы всегда хотим понимать:
    - откуда взяли (source)
    - где лежало (path)
    - что именно (snippet)
    """
    model_config = ConfigDict(extra="forbid")

    source: EvidenceSource
    path: str
    snippet: str


class FieldMatch(BaseModel):
    """
    Результат сопоставления одного канонического Field к конкретному listing.
    """
    model_config = ConfigDict(extra="forbid")

    value: Ternary
    confidence: float = 0.0
    evidence: List[Evidence] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("confidence must be in [0.0, 1.0]")
        return v


class MatchReport(BaseModel):
    """
    Итог по листингу:
    - matches: по каждому Field свой FieldMatch
    - score: общий скор для ранжирования
    - hard_fail_fields: какие must-have не выполнены (для фильтрации)
    """
    model_config = ConfigDict(extra="forbid")

    listing_id: Optional[str] = None
    matches: Dict[CanonicalField, FieldMatch] = Field(default_factory=dict)

    score: float = 0.0
    hard_fail_fields: List[CanonicalField] = Field(default_factory=list)

    def is_eligible(self) -> bool:
        """
        Удобный метод: прошёл ли listing must-have фильтр.
        """
        return len(self.hard_fail_fields) == 0
