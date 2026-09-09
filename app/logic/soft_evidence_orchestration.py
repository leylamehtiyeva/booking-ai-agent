"""
Full soft-evidence pipeline orchestration for one request's shadow-mode
scope: retrieval -> cleanup/routing -> fair Gemini scheduling -> claim
aggregation -> SoftPreferenceEvidence, one object per hotel.

Not wired into evaluate_listings() yet - see
app.logic.listing_evaluation for the (separate, later) integration
point.
"""

from __future__ import annotations

from app.logic.semantic_evidence_verification import verify_evidence_relation
from app.logic.soft_evidence_cleanup import DedupedEvidence, clean_and_route_candidates
from app.logic.soft_evidence_collection import collect_soft_evidence_pool
from app.logic.soft_evidence_retrieval import (
    EmbedBatchOutcome,
    embed_evidence_pool,
    embed_query_texts,
    retrieve_top_k,
)
from app.logic.soft_preference_decomposition import (
    CANONICAL_CLAIM_ORDER,
    CLAIM_HYPOTHESES,
    AtomicClaimAssignment,
    get_retrieval_query,
)
from app.observability.trace import RequestTrace
from app.schemas.listing import ListingRaw
from app.schemas.semantic_verifier_policy import SemanticVerifierPolicy
from app.schemas.soft_evidence import (
    AtomicClaimResult,
    ClaimResolutionMethod,
    EvidenceItem,
    EvidenceResolutionStatus,
    RetrievalStatus,
    SemanticVerifierUsage,
    SoftPreferenceEvidence,
)
from app.schemas.soft_evidence_pipeline_policy import SoftEvidencePipelinePolicy

# Total number of validated Phase B claims - the upper bound used both
# by effective_per_hotel_budget() and by the request-budget floor.
MAX_CLAIMS = len(CLAIM_HYPOTHESES)


def compute_pool_retrieval_status(outcomes: list[EmbedBatchOutcome]) -> tuple[RetrievalStatus, list[str]]:
    """
    An empty pool (no batches at all) is SUCCESS with no errors - a
    hotel genuinely having no evidence text is not a technical failure.
    """
    if not outcomes:
        return RetrievalStatus.SUCCESS, []

    failures = [o for o in outcomes if not o.success]
    if not failures:
        return RetrievalStatus.SUCCESS, []

    errors = [f"evidence pool batch failed: {o.error}" for o in failures]
    successes = [o for o in outcomes if o.success]
    if successes:
        return RetrievalStatus.PARTIAL, errors
    return RetrievalStatus.FAILED, errors


def compute_claim_retrieval_status(
    *,
    query_outcome: EmbedBatchOutcome,
    pool_status: RetrievalStatus,
    pool_errors: list[str],
) -> tuple[RetrievalStatus, list[str]]:
    """
    Query embedding is shared/request-level and all-or-nothing: if it
    failed, no claim on any hotel has a query vector to compare
    against anything, regardless of that hotel's own pool status.
    """
    if not query_outcome.success:
        return RetrievalStatus.FAILED, [f"query embedding failed: {query_outcome.error}"]
    return pool_status, pool_errors


def effective_per_hotel_budget(*, base: int, n_active_claims: int) -> int:
    """
    Do not let a fixed base budget silently starve active claims: a
    hotel with more genuinely active claims (needing Gemini) than the
    base allows gets a larger effective budget, capped at MAX_CLAIMS
    (there are only MAX_CLAIMS claims total, so more would be
    meaningless).
    """
    return min(MAX_CLAIMS, max(base, n_active_claims))


class _HotelClaimContext:
    """Internal, per-(hotel, claim) working state during orchestration."""

    __slots__ = ("deterministic_items", "free_text_candidates", "retrieval_status", "retrieval_errors", "retrieved_candidate_count")

    def __init__(self) -> None:
        self.deterministic_items: list[EvidenceItem] = []
        self.free_text_candidates: list[DedupedEvidence] = []
        self.retrieval_status: RetrievalStatus = RetrievalStatus.SUCCESS
        self.retrieval_errors: list[str] = []
        self.retrieved_candidate_count: int = 0


async def schedule_gemini_verification(
    *,
    free_text_candidates: dict[int, dict[str, list[DedupedEvidence]]],
    claim_hypotheses: dict[str, str] = CLAIM_HYPOTHESES,
    canonical_claim_order: tuple[str, ...] = CANONICAL_CLAIM_ORDER,
    retrieval_top_k: int,
    verifier_policy: SemanticVerifierPolicy,
    trace: RequestTrace | None,
) -> tuple[dict[int, dict[str, list[EvidenceItem]]], dict[int, dict]]:
    """
    Fair, deterministic round-based scheduling:
        candidate_rank -> claim (canonical order) -> hotel (rank order)
    i.e. every active claim on every hotel gets its rank-0 (best)
    candidate attempted before ANY claim gets its rank-1 candidate
    attempted anywhere. Per-hotel budget is "effective" (widened past
    the base if a hotel genuinely has more active claims than the
    base would cover); the request budget is a safety ceiling only -
    sized by the caller so it does not bind before the per-hotel
    budgets do under the standard scope.

    Once a budget is exhausted the traversal does NOT stop - every
    remaining (rank, claim, hotel) combination still gets visited and
    still gets an explicit SKIPPED_CALL_LIMIT EvidenceItem. A claim
    with zero free-text candidates for a hotel (nothing retrieved,
    everything deterministic, or everything filtered/deduped away)
    simply never enters this loop for that hotel - not a special case.

    Returns (gemini_items, verifier_usage_accum): gemini_items maps
    hotel_idx -> claim_id -> list[EvidenceItem] (Gemini-resolved or
    skipped); verifier_usage_accum maps hotel_idx -> a running dict of
    calls/latency_ms/input_tokens/output_tokens/total_tokens/
    estimated_cost_usd/parse_failures/errors, built by reading back
    trace.llm_calls[-1] immediately after each awaited verifier call
    (safe because calls are sequential, never concurrent).
    """
    hotel_indices = sorted(free_text_candidates.keys())

    base = verifier_policy.normalized_max_calls_per_hotel()
    hotel_budgets: dict[int, int] = {}
    for hotel_idx in hotel_indices:
        n_active_claims = sum(1 for claim_id in canonical_claim_order if free_text_candidates[hotel_idx].get(claim_id))
        hotel_budgets[hotel_idx] = effective_per_hotel_budget(base=base, n_active_claims=n_active_claims)

    # The request budget is the safety ceiling exactly as configured -
    # it is never silently widened here. "Consistent with the effective
    # hotel budgets" is achieved by SemanticVerifierPolicy's own default
    # (60 = 5 hotels x MAX_CLAIMS), not by overriding whatever a caller
    # explicitly configures; a deliberately tighter cap must still bind.
    request_budget = verifier_policy.normalized_max_calls_per_request()

    gemini_items: dict[int, dict[str, list[EvidenceItem]]] = {
        hotel_idx: {claim_id: [] for claim_id in canonical_claim_order} for hotel_idx in hotel_indices
    }
    verifier_usage_accum: dict[int, dict] = {
        hotel_idx: {
            "calls": 0, "latency_ms": 0.0, "input_tokens": 0, "output_tokens": 0,
            "total_tokens": 0, "estimated_cost_usd": 0.0, "parse_failures": 0, "errors": [],
        }
        for hotel_idx in hotel_indices
    }

    for rank in range(retrieval_top_k):
        for claim_id in canonical_claim_order:
            hypothesis = claim_hypotheses[claim_id]
            for hotel_idx in hotel_indices:
                candidates = free_text_candidates[hotel_idx].get(claim_id, [])
                if rank >= len(candidates):
                    continue
                candidate = candidates[rank]

                if request_budget <= 0 or hotel_budgets[hotel_idx] <= 0:
                    item = EvidenceItem(
                        evidence_text=candidate.text,
                        relation=None,
                        resolution_method=ClaimResolutionMethod.GEMINI,
                        resolution_status=EvidenceResolutionStatus.SKIPPED_CALL_LIMIT,
                        error="skipped: verifier call limit reached",
                        source_type=candidate.source_type,
                        source_path=candidate.source_path,
                        retrieval_score=candidate.retrieval_score,
                    )
                else:
                    request_budget -= 1
                    hotel_budgets[hotel_idx] -= 1

                    result = await verify_evidence_relation(
                        candidate.text, hypothesis, policy=verifier_policy, trace=trace,
                    )

                    item = EvidenceItem(
                        evidence_text=candidate.text,
                        relation=result.relation,
                        resolution_method=ClaimResolutionMethod.GEMINI,
                        resolution_status=result.status,
                        error=result.error,
                        source_type=candidate.source_type,
                        source_path=candidate.source_path,
                        retrieval_score=candidate.retrieval_score,
                        verifier_reason=result.reason,
                    )

                    accum = verifier_usage_accum[hotel_idx]
                    accum["calls"] += 1
                    if trace is not None and trace.llm_calls:
                        last_call = trace.llm_calls[-1]
                        accum["latency_ms"] += last_call.latency_ms or 0.0
                        accum["input_tokens"] += last_call.prompt_tokens or 0
                        accum["output_tokens"] += last_call.completion_tokens or 0
                        accum["total_tokens"] += last_call.total_tokens or 0
                        accum["estimated_cost_usd"] += last_call.estimated_cost_usd or 0.0
                        if last_call.parse_failure:
                            accum["parse_failures"] += 1
                        if last_call.error:
                            accum["errors"].append(last_call.error)

                gemini_items[hotel_idx][claim_id].append(item)

    return gemini_items, verifier_usage_accum


async def build_shadow_soft_preference_evidence(
    *,
    listings: list[ListingRaw],
    claim_assignments: list[AtomicClaimAssignment],
    pipeline_policy: SoftEvidencePipelinePolicy,
    verifier_policy: SemanticVerifierPolicy,
    trace: RequestTrace | None = None,
) -> list[SoftPreferenceEvidence]:
    """
    Builds one SoftPreferenceEvidence per listing (positionally
    aligned with `listings`). Callers decide whether to call this at
    all (e.g. skip entirely when claim_assignments is empty or a
    listing is outside shadow scope) - this function always returns a
    populated result for every listing it's given; None-vs-populated
    is an integration-layer decision, not made here.
    """
    claim_ids = [claim_id for claim_id in CANONICAL_CLAIM_ORDER if any(a.claim_id == claim_id for a in claim_assignments)]

    query_vectors_by_claim, query_outcome = embed_query_texts(
        [(claim_id, get_retrieval_query(claim_id)) for claim_id in claim_ids],
        model=pipeline_policy.embedding_model,
        trace=trace,
    )

    contexts: dict[int, dict[str, _HotelClaimContext]] = {}

    for hotel_idx, listing in enumerate(listings):
        contexts[hotel_idx] = {claim_id: _HotelClaimContext() for claim_id in claim_ids}

        pool = collect_soft_evidence_pool(listing)
        pool_vectors, pool_outcomes = embed_evidence_pool(pool, model=pipeline_policy.embedding_model, trace=trace)
        pool_status, pool_errors = compute_pool_retrieval_status(pool_outcomes)

        for claim_id in claim_ids:
            ctx = contexts[hotel_idx][claim_id]
            ctx.retrieval_status, ctx.retrieval_errors = compute_claim_retrieval_status(
                query_outcome=query_outcome, pool_status=pool_status, pool_errors=pool_errors,
            )

            if not query_outcome.success:
                continue  # no query vector at all - nothing to retrieve for this claim

            retrieved = retrieve_top_k(
                query_vectors_by_claim[claim_id], pool, pool_vectors, k=pipeline_policy.retrieval_top_k,
            )
            ctx.retrieved_candidate_count = len(retrieved)

            routed = clean_and_route_candidates(claim_id, retrieved)
            ctx.deterministic_items = routed.deterministic_items
            ctx.free_text_candidates = routed.free_text_candidates

    free_text_candidates_by_hotel = {
        hotel_idx: {claim_id: contexts[hotel_idx][claim_id].free_text_candidates for claim_id in claim_ids}
        for hotel_idx in contexts
    }

    gemini_items, verifier_usage_accum = await schedule_gemini_verification(
        free_text_candidates=free_text_candidates_by_hotel,
        retrieval_top_k=pipeline_policy.retrieval_top_k,
        verifier_policy=verifier_policy,
        trace=trace,
    )

    results: list[SoftPreferenceEvidence] = []
    for hotel_idx in range(len(listings)):
        claims: list[AtomicClaimResult] = []
        for claim_id in claim_ids:
            ctx = contexts[hotel_idx][claim_id]
            evidence_items = ctx.deterministic_items + gemini_items.get(hotel_idx, {}).get(claim_id, [])
            claims.append(
                AtomicClaimResult.from_evidence_items(
                    claim_id=claim_id,
                    hypothesis=CLAIM_HYPOTHESES[claim_id],
                    evidence_items=evidence_items,
                    retrieval_status=ctx.retrieval_status,
                    retrieval_errors=ctx.retrieval_errors,
                    retrieved_candidate_count=ctx.retrieved_candidate_count,
                )
            )

        accum = verifier_usage_accum.get(hotel_idx, {"calls": 0})
        semantic_verifier = (
            SemanticVerifierUsage(
                model=verifier_policy.model,
                calls=accum["calls"],
                latency_ms=round(accum["latency_ms"], 2),
                input_tokens=accum["input_tokens"],
                output_tokens=accum["output_tokens"],
                total_tokens=accum["total_tokens"],
                estimated_cost_usd=round(accum["estimated_cost_usd"], 6) if accum["calls"] else None,
                parse_failures=accum["parse_failures"],
                errors=accum["errors"],
            )
            if accum["calls"] > 0
            else None
        )

        results.append(SoftPreferenceEvidence(claims=claims, semantic_verifier=semantic_verifier))

    return results
