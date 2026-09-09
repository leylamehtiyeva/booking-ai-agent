from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceRelation(str, Enum):
    """Semantic relation of ONE evidence snippet to ONE atomic claim."""

    SUPPORT = "SUPPORT"
    CONTRADICT = "CONTRADICT"
    NOT_ENOUGH_EVIDENCE = "NOT_ENOUGH_EVIDENCE"


class ClaimRelation(str, Enum):
    """
    Aggregated relation across all successfully resolved evidence for one
    claim. MIXED is a distinct outcome from CONTRADICT: it means both
    supporting and contradicting evidence were found, which must not be
    collapsed away before a future ranking layer sees it.
    """

    SUPPORT = "SUPPORT"
    CONTRADICT = "CONTRADICT"
    NOT_ENOUGH_EVIDENCE = "NOT_ENOUGH_EVIDENCE"
    MIXED = "MIXED"


class ClaimResolutionMethod(str, Enum):
    DETERMINISTIC = "deterministic"
    GEMINI = "gemini"


class EvidenceResolutionStatus(str, Enum):
    """
    Whether this evidence item's relation was actually determined.
    RESOLVED <=> relation is not None; anything else <=> relation is None
    (enforced by EvidenceItem's validator below). This is what lets
    "there was no evidence" (empty evidence_items on the claim) be
    distinguished from "there was evidence, but verification failed".
    """

    RESOLVED = "resolved"
    VERIFICATION_FAILED = "verification_failed"
    SKIPPED_CALL_LIMIT = "skipped_call_limit"


class EvidenceItem(BaseModel):
    """
    One retrieved evidence snippet for one atomic claim. Always kept, even
    if verification failed or was skipped for a call-limit reason -
    resolution_status/error distinguish that from a successfully resolved
    NOT_ENOUGH_EVIDENCE relation.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_text: str
    relation: EvidenceRelation | None = None
    resolution_method: ClaimResolutionMethod
    resolution_status: EvidenceResolutionStatus = EvidenceResolutionStatus.RESOLVED
    error: str | None = None

    source_type: str | None = None
    source_path: str | None = None
    retrieval_score: float | None = None
    verifier_reason: str | None = None

    @model_validator(mode="after")
    def _relation_matches_status(self) -> "EvidenceItem":
        resolved = self.resolution_status == EvidenceResolutionStatus.RESOLVED
        if resolved and self.relation is None:
            raise ValueError(
                "relation must be set when resolution_status is RESOLVED"
            )
        if not resolved and self.relation is not None:
            raise ValueError(
                "relation must be None when resolution_status is not RESOLVED"
            )
        return self


class AtomicClaimResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    hypothesis: str
    relation: ClaimRelation
    evidence_items: list[EvidenceItem] = Field(default_factory=list)

    @classmethod
    def from_evidence_items(
        cls,
        *,
        claim_id: str,
        hypothesis: str,
        evidence_items: list[EvidenceItem],
    ) -> "AtomicClaimResult":
        """
        The only place a claim's top-level relation should be assigned
        from evidence - see aggregate_claim_relation for the rule.
        """
        return cls(
            claim_id=claim_id,
            hypothesis=hypothesis,
            relation=aggregate_claim_relation(evidence_items),
            evidence_items=evidence_items,
        )


class SemanticVerifierUsage(BaseModel):
    """
    Aggregated Gemini verifier usage for ONE hotel's evidence resolution
    (i.e. one SoftPreferenceEvidence). Per-call detail lives in
    RequestTrace.llm_calls, not duplicated here.
    """

    model_config = ConfigDict(extra="forbid")

    model: str
    calls: int = 0
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float | None = None
    parse_failures: int = 0
    errors: list[str] = Field(default_factory=list)


class SoftPreferenceEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[AtomicClaimResult] = Field(default_factory=list)
    semantic_verifier: SemanticVerifierUsage | None = None


def aggregate_claim_relation(evidence_items: list[EvidenceItem]) -> ClaimRelation:
    """
    - no resolved evidence -> NOT_ENOUGH_EVIDENCE
    - at least one SUPPORT + at least one CONTRADICT -> MIXED
    - SUPPORT and no CONTRADICT -> SUPPORT
    - CONTRADICT and no SUPPORT -> CONTRADICT
    - only NOT_ENOUGH_EVIDENCE (or nothing resolved) -> NOT_ENOUGH_EVIDENCE

    Only items with resolution_status == RESOLVED participate.
    VERIFICATION_FAILED / SKIPPED_CALL_LIMIT items are excluded from the
    vote but remain visible in evidence_items - they are not deleted.
    """
    resolved_relations = {
        item.relation
        for item in evidence_items
        if item.resolution_status == EvidenceResolutionStatus.RESOLVED
        and item.relation is not None
    }

    has_support = EvidenceRelation.SUPPORT in resolved_relations
    has_contradict = EvidenceRelation.CONTRADICT in resolved_relations

    if has_support and has_contradict:
        return ClaimRelation.MIXED
    if has_support:
        return ClaimRelation.SUPPORT
    if has_contradict:
        return ClaimRelation.CONTRADICT
    return ClaimRelation.NOT_ENOUGH_EVIDENCE
