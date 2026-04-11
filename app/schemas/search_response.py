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

    # Compatibility-only derived projection from canonical constraints.
    # This is NOT source-of-truth request meaning.
    # It should reflect only the legacy-compatible unresolved MUST slice,
    # not arbitrary dropped parse/debug items.
    unknown_requests: list[str] = Field(default_factory=list)

    # Debug / normalization residue.
    # These are items that were dropped or could not be preserved cleanly in the
    # normalized request summary, and must not be interpreted as canonical unresolved
    # user intent.
    dropped_requests: list[str] = Field(default_factory=list)

    # Canonical semantic state.
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
    status: str  # matched | uncertain | failed
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
    
    eligibility_status: str | None = None
    match_tier: str | None = None
    selection_reasons: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)

    why: list[str] = Field(default_factory=list)
    constraint_resolution_results: list[ConstraintResolutionItem] = Field(default_factory=list)


class NormalizedSearchResponse(BaseModel):
    need_clarification: bool
    questions: list[str] = Field(default_factory=list)

    request_summary: NormalizedRequestSummary | None = None
    results: list[NormalizedSearchResult] = Field(default_factory=list)

    debug_notes: list[str] = Field(default_factory=list)
    
    
class ConstraintResolutionEvidence(BaseModel):
    snippet: str
    source: str
    path: str | None = None


class ConstraintResolutionItem(BaseModel):
    listing_id: str | None = None
    listing_title: str | None = None
    constraint_id: str | None = None

    raw_text: str
    normalized_text: str

    resolver_type: str
    decision: str
    resolution_status: str
    confidence: float | None = None
    reason: str

    evidence: list[ConstraintResolutionEvidence] = Field(default_factory=list)

    source_stage: str = "fallback"
    structured_value_before: str | None = None
    explicit_negative: bool = False