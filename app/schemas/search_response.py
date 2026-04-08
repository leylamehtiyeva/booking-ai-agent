from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, Field as PydanticField

class NormalizedRequestSummary(BaseModel):
    city: str | None = None
    check_in: str | None = None
    check_out: str | None = None

    must_have_fields: list[str] = Field(default_factory=list)
    nice_to_have_fields: list[str] = Field(default_factory=list)

    property_types: list[str] = Field(default_factory=list)
    occupancy_types: list[str] = Field(default_factory=list)

    filters: dict[str, Any] = Field(default_factory=dict)
    unknown_requests: list[str] = Field(default_factory=list)
    constraints: list[dict] = PydanticField(default_factory=list)

class UnknownFieldEvidence(BaseModel):
    source_path: str
    snippet: str


class UnknownRequestResult(BaseModel):
    query_text: str
    value: str  # FOUND | NOT_FOUND | UNCERTAIN
    reason: str
    evidence: list[UnknownFieldEvidence] = []
    constraint: dict[str, Any] | None = None

class ConstraintStatus(BaseModel):
    name: str
    status: str   # matched | uncertain | failed
    reason: str | None = None
    constraint: dict[str, Any] | None = None


class ResultFact(BaseModel):
    key: str
    value: Any
    source: str | None = None


class NormalizedSearchResult(BaseModel):
    result_id: str
    title: str
    url: str | None = None

    score: float
    matched_must_count: int
    matched_must_total: int

    unknown_request_results: list[UnknownRequestResult] = Field(default_factory=list)    
    matched_constraints: list[ConstraintStatus] = Field(default_factory=list)
    uncertain_constraints: list[ConstraintStatus] = Field(default_factory=list)
    failed_constraints: list[ConstraintStatus] = Field(default_factory=list)
    facts: list[ResultFact] = Field(default_factory=list)

    why: list[str] = Field(default_factory=list)


class NormalizedSearchResponse(BaseModel):
    need_clarification: bool
    questions: list[str] = Field(default_factory=list)

    request_summary: NormalizedRequestSummary | None = None
    results: list[NormalizedSearchResult] = Field(default_factory=list)

    debug_notes: list[str] = Field(default_factory=list)