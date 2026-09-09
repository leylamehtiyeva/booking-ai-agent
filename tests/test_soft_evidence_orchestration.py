from __future__ import annotations

import pytest

from app.logic import soft_evidence_orchestration as orch
from app.logic.soft_evidence_cleanup import DedupedEvidence
from app.logic.soft_evidence_retrieval import EmbedBatchOutcome
from app.logic.soft_preference_decomposition import AtomicClaimAssignment, PreferenceDirection
from app.observability.trace import RequestTrace
from app.schemas.listing import ListingRaw
from app.schemas.semantic_verifier_policy import SemanticVerifierPolicy
from app.schemas.soft_evidence import (
    EvidenceRelation,
    EvidenceResolutionStatus,
    RetrievalStatus,
)
from app.schemas.soft_evidence_pipeline_policy import SoftEvidencePipelinePolicy
from app.logic.semantic_evidence_verification import SemanticVerificationResult


def _ok(latency_ms=10.0, batch_size=1) -> EmbedBatchOutcome:
    return EmbedBatchOutcome(success=True, batch_size=batch_size, latency_ms=latency_ms, error=None, token_count=None, estimated_cost_usd=None)


def _fail(error="boom") -> EmbedBatchOutcome:
    return EmbedBatchOutcome(success=False, batch_size=1, latency_ms=5.0, error=error, token_count=None, estimated_cost_usd=None)


def _candidate(text: str, score: float, source_type="description") -> DedupedEvidence:
    return DedupedEvidence(text=text, source_type=source_type, source_path=None, retrieval_score=score)


# ---------------- compute_pool_retrieval_status ----------------


def test_pool_status_empty_is_success():
    status, errors = orch.compute_pool_retrieval_status([])
    assert status == RetrievalStatus.SUCCESS
    assert errors == []


def test_pool_status_all_success():
    status, errors = orch.compute_pool_retrieval_status([_ok(), _ok()])
    assert status == RetrievalStatus.SUCCESS
    assert errors == []


def test_pool_status_mixed_is_partial():
    status, errors = orch.compute_pool_retrieval_status([_ok(), _fail("batch 2 timed out")])
    assert status == RetrievalStatus.PARTIAL
    assert len(errors) == 1
    assert "batch 2 timed out" in errors[0]


def test_pool_status_all_failed():
    status, errors = orch.compute_pool_retrieval_status([_fail("a"), _fail("b")])
    assert status == RetrievalStatus.FAILED
    assert len(errors) == 2


# ---------------- compute_claim_retrieval_status ----------------


def test_claim_status_query_failure_overrides_pool_status():
    status, errors = orch.compute_claim_retrieval_status(
        query_outcome=_fail("query down"), pool_status=RetrievalStatus.SUCCESS, pool_errors=[],
    )
    assert status == RetrievalStatus.FAILED
    assert "query embedding failed" in errors[0]


def test_claim_status_query_success_uses_pool_status():
    status, errors = orch.compute_claim_retrieval_status(
        query_outcome=_ok(), pool_status=RetrievalStatus.PARTIAL, pool_errors=["x"],
    )
    assert status == RetrievalStatus.PARTIAL
    assert errors == ["x"]


# ---------------- effective_per_hotel_budget ----------------


def test_effective_budget_uses_base_when_active_claims_fewer():
    assert orch.effective_per_hotel_budget(base=6, n_active_claims=2) == 6


def test_effective_budget_widens_for_more_active_claims():
    assert orch.effective_per_hotel_budget(base=6, n_active_claims=9) == 9


def test_effective_budget_capped_at_max_claims():
    assert orch.effective_per_hotel_budget(base=6, n_active_claims=999) == orch.MAX_CLAIMS


# ---------------- schedule_gemini_verification: fairness ----------------


async def test_rank0_covered_across_all_claims_and_hotels_before_rank1(monkeypatch):
    call_order: list[tuple[int, str, int]] = []  # (hotel_idx, claim_id, rank-ish by text)

    async def _fake_verify(evidence_text, hypothesis, *, policy, trace):
        call_order.append(evidence_text)
        return SemanticVerificationResult(relation=EvidenceRelation.SUPPORT, reason="ok", status=EvidenceResolutionStatus.RESOLVED)

    monkeypatch.setattr(orch, "verify_evidence_relation", _fake_verify)

    # Two hotels, two claims, each with 2 candidates (rank0/rank1)
    free_text_candidates = {
        0: {"Q1": [_candidate("h0-q1-r0", 0.9), _candidate("h0-q1-r1", 0.5)],
            "BC1": [_candidate("h0-bc1-r0", 0.9), _candidate("h0-bc1-r1", 0.5)]},
        1: {"Q1": [_candidate("h1-q1-r0", 0.9), _candidate("h1-q1-r1", 0.5)],
            "BC1": [_candidate("h1-bc1-r0", 0.9), _candidate("h1-bc1-r1", 0.5)]},
    }

    policy = SemanticVerifierPolicy(max_calls_per_hotel=6, max_calls_per_request=60)
    await orch.schedule_gemini_verification(
        free_text_candidates=free_text_candidates,
        canonical_claim_order=("BC1", "Q1"),
        retrieval_top_k=2,
        verifier_policy=policy,
        trace=None,
    )

    # every "-r0" call must happen before any "-r1" call
    r0_positions = [i for i, t in enumerate(call_order) if t.endswith("-r0")]
    r1_positions = [i for i, t in enumerate(call_order) if t.endswith("-r1")]
    assert max(r0_positions) < min(r1_positions)
    assert len(call_order) == 8


async def test_claim_major_order_within_a_rank(monkeypatch):
    """
    Within rank 0: claim BC1 across all hotels, THEN claim Q1 across
    all hotels (canonical_claim_order=("BC1","Q1")) - not hotel-major.
    """
    call_order: list[str] = []

    async def _fake_verify(evidence_text, hypothesis, *, policy, trace):
        call_order.append(evidence_text)
        return SemanticVerificationResult(relation=EvidenceRelation.SUPPORT, reason="ok", status=EvidenceResolutionStatus.RESOLVED)

    monkeypatch.setattr(orch, "verify_evidence_relation", _fake_verify)

    free_text_candidates = {
        0: {"Q1": [_candidate("h0-q1", 0.9)], "BC1": [_candidate("h0-bc1", 0.9)]},
        1: {"Q1": [_candidate("h1-q1", 0.9)], "BC1": [_candidate("h1-bc1", 0.9)]},
    }
    policy = SemanticVerifierPolicy(max_calls_per_hotel=6, max_calls_per_request=60)
    await orch.schedule_gemini_verification(
        free_text_candidates=free_text_candidates,
        canonical_claim_order=("BC1", "Q1"),
        retrieval_top_k=1,
        verifier_policy=policy,
        trace=None,
    )
    assert call_order == ["h0-bc1", "h1-bc1", "h0-q1", "h1-q1"]


async def test_no_starvation_when_one_claim_has_many_candidates(monkeypatch):
    """
    A claim with 3 candidates on hotel 0 must not exhaust the budget
    before a different claim on hotel 1 gets its rank-0 attempt.
    """
    async def _fake_verify(evidence_text, hypothesis, *, policy, trace):
        return SemanticVerificationResult(relation=EvidenceRelation.NOT_ENOUGH_EVIDENCE, reason=None, status=EvidenceResolutionStatus.RESOLVED)

    monkeypatch.setattr(orch, "verify_evidence_relation", _fake_verify)

    free_text_candidates = {
        0: {"Q1": [_candidate("h0-q1-r0", 0.9), _candidate("h0-q1-r1", 0.8), _candidate("h0-q1-r2", 0.7)], "BC1": []},
        1: {"Q1": [], "BC1": [_candidate("h1-bc1-r0", 0.9)]},
    }
    policy = SemanticVerifierPolicy(max_calls_per_hotel=6, max_calls_per_request=60)
    gemini_items, _ = await orch.schedule_gemini_verification(
        free_text_candidates=free_text_candidates,
        canonical_claim_order=("BC1", "Q1"),
        retrieval_top_k=3,
        verifier_policy=policy,
        trace=None,
    )
    # hotel 1's BC1 rank-0 candidate must have been RESOLVED, not starved
    item = gemini_items[1]["BC1"][0]
    assert item.resolution_status == EvidenceResolutionStatus.RESOLVED


# ---------------- schedule_gemini_verification: budget caps ----------------


async def test_per_hotel_cap_produces_skipped_items(monkeypatch):
    calls = {"n": 0}

    async def _fake_verify(evidence_text, hypothesis, *, policy, trace):
        calls["n"] += 1
        return SemanticVerificationResult(relation=EvidenceRelation.SUPPORT, reason="ok", status=EvidenceResolutionStatus.RESOLVED)

    monkeypatch.setattr(orch, "verify_evidence_relation", _fake_verify)

    # one hotel, one claim, 3 candidates, base budget=2 -> effective budget = max(2,1 active claim)=2
    free_text_candidates = {0: {"Q1": [_candidate("a", 0.9), _candidate("b", 0.8), _candidate("c", 0.7)]}}
    policy = SemanticVerifierPolicy(max_calls_per_hotel=2, max_calls_per_request=60)
    gemini_items, _ = await orch.schedule_gemini_verification(
        free_text_candidates=free_text_candidates,
        canonical_claim_order=("Q1",),
        retrieval_top_k=3,
        verifier_policy=policy,
        trace=None,
    )
    items = gemini_items[0]["Q1"]
    assert len(items) == 3
    assert calls["n"] == 2
    statuses = [i.resolution_status for i in items]
    assert statuses.count(EvidenceResolutionStatus.RESOLVED) == 2
    assert statuses.count(EvidenceResolutionStatus.SKIPPED_CALL_LIMIT) == 1
    skipped = [i for i in items if i.resolution_status == EvidenceResolutionStatus.SKIPPED_CALL_LIMIT][0]
    assert skipped.relation is None
    assert skipped.error is not None
    # candidate text/source preserved even though skipped
    assert skipped.evidence_text == "c"


async def test_request_cap_applies_across_hotels(monkeypatch):
    calls = {"n": 0}

    async def _fake_verify(evidence_text, hypothesis, *, policy, trace):
        calls["n"] += 1
        return SemanticVerificationResult(relation=EvidenceRelation.SUPPORT, reason="ok", status=EvidenceResolutionStatus.RESOLVED)

    monkeypatch.setattr(orch, "verify_evidence_relation", _fake_verify)

    free_text_candidates = {
        0: {"Q1": [_candidate("h0", 0.9)]},
        1: {"Q1": [_candidate("h1", 0.9)]},
        2: {"Q1": [_candidate("h2", 0.9)]},
    }
    policy = SemanticVerifierPolicy(max_calls_per_hotel=6, max_calls_per_request=2)
    gemini_items, _ = await orch.schedule_gemini_verification(
        free_text_candidates=free_text_candidates,
        canonical_claim_order=("Q1",),
        retrieval_top_k=1,
        verifier_policy=policy,
        trace=None,
    )
    assert calls["n"] == 2
    all_items = [gemini_items[h]["Q1"][0] for h in (0, 1, 2)]
    resolved = [i for i in all_items if i.resolution_status == EvidenceResolutionStatus.RESOLVED]
    skipped = [i for i in all_items if i.resolution_status == EvidenceResolutionStatus.SKIPPED_CALL_LIMIT]
    assert len(resolved) == 2
    assert len(skipped) == 1


async def test_verifier_usage_accumulated_per_hotel(monkeypatch):
    async def _fake_verify(evidence_text, hypothesis, *, policy, trace):
        if trace is not None:
            from app.observability.trace import LLMCallTrace
            trace.add_llm_call(LLMCallTrace(
                step="semantic_evidence_verifier", model="gemini-2.5-flash",
                prompt_tokens=100, completion_tokens=10, total_tokens=110,
                estimated_cost_usd=0.001, success=True, latency_ms=50.0, parse_failure=False,
            ))
        return SemanticVerificationResult(relation=EvidenceRelation.SUPPORT, reason="ok", status=EvidenceResolutionStatus.RESOLVED)

    monkeypatch.setattr(orch, "verify_evidence_relation", _fake_verify)

    trace = RequestTrace()
    free_text_candidates = {0: {"Q1": [_candidate("a", 0.9)]}}
    policy = SemanticVerifierPolicy(max_calls_per_hotel=6, max_calls_per_request=60)
    _, usage = await orch.schedule_gemini_verification(
        free_text_candidates=free_text_candidates,
        canonical_claim_order=("Q1",),
        retrieval_top_k=1,
        verifier_policy=policy,
        trace=trace,
    )
    assert usage[0]["calls"] == 1
    assert usage[0]["latency_ms"] == 50.0
    assert usage[0]["total_tokens"] == 110
    assert usage[0]["estimated_cost_usd"] == pytest.approx(0.001)


# ---------------- build_shadow_soft_preference_evidence: end-to-end ----------------


def _assignment(claim_id: str) -> AtomicClaimAssignment:
    from app.logic.soft_preference_decomposition import CLAIM_HYPOTHESES
    return AtomicClaimAssignment(
        claim_id=claim_id,
        hypothesis=CLAIM_HYPOTHESES[claim_id],
        family="quiet",
        source_constraint_id="c1",
        source_constraint_text="quiet please",
        preference_direction=PreferenceDirection.DESIRED,
    )


async def test_query_embedding_failure_makes_every_claim_failed_with_no_evidence(monkeypatch):
    monkeypatch.setattr(orch, "embed_query_texts", lambda queries, *, model, trace: ({}, _fail("query api down")))

    listings = [ListingRaw(id="h1"), ListingRaw(id="h2")]
    assignments = [_assignment("Q1")]

    results = await orch.build_shadow_soft_preference_evidence(
        listings=listings,
        claim_assignments=assignments,
        pipeline_policy=SoftEvidencePipelinePolicy(),
        verifier_policy=SemanticVerifierPolicy(),
        trace=None,
    )

    assert len(results) == 2
    for evidence in results:
        assert len(evidence.claims) == 1
        claim = evidence.claims[0]
        assert claim.claim_id == "Q1"
        assert claim.retrieval_status == RetrievalStatus.FAILED
        assert claim.retrieval_errors
        assert claim.evidence_items == []
        assert claim.relation.value == "NOT_ENOUGH_EVIDENCE"
        assert evidence.semantic_verifier is None  # no Gemini calls were ever attempted


async def test_deterministic_only_resolution_leaves_semantic_verifier_none(monkeypatch):
    monkeypatch.setattr(orch, "embed_query_texts", lambda queries, *, model, trace: ({"RW1": [1.0]}, _ok()))
    monkeypatch.setattr(orch, "embed_evidence_pool", lambda pool, *, model, trace: ([[1.0]] * len(pool), [_ok()] if pool else []))
    monkeypatch.setattr(
        orch, "retrieve_top_k",
        lambda query_vector, pool, vectors, k: _fixed_retrieval(pool),
    )

    listings = [ListingRaw(id="h1", rooms=[])]
    assignments = [_assignment("RW1")]

    async def _fake_verify(*args, **kwargs):
        raise AssertionError("Gemini should never be called for a fully deterministic candidate set")

    monkeypatch.setattr(orch, "verify_evidence_relation", _fake_verify)

    results = await orch.build_shadow_soft_preference_evidence(
        listings=listings,
        claim_assignments=assignments,
        pipeline_policy=SoftEvidencePipelinePolicy(),
        verifier_policy=SemanticVerifierPolicy(),
        trace=None,
    )

    evidence = results[0]
    claim = evidence.claims[0]
    assert claim.relation.value == "SUPPORT"
    assert claim.evidence_items[0].resolution_method.value == "deterministic"
    assert evidence.semantic_verifier is None


def _fixed_retrieval(pool):
    from app.logic.soft_evidence_retrieval import RetrievedEvidence
    return [
        RetrievedEvidence(text="Desk", source_type="room_facilities", source_path="rooms[0].facilities[0].name", retrieval_score=0.99)
    ]


async def test_empty_claim_assignments_produces_empty_claims_no_calls(monkeypatch):
    called = {"embed_query": False}

    def _tracked_embed_query(queries, *, model, trace):
        called["embed_query"] = True
        return {}, _ok()

    monkeypatch.setattr(orch, "embed_query_texts", _tracked_embed_query)

    results = await orch.build_shadow_soft_preference_evidence(
        listings=[ListingRaw(id="h1")],
        claim_assignments=[],
        pipeline_policy=SoftEvidencePipelinePolicy(),
        verifier_policy=SemanticVerifierPolicy(),
        trace=None,
    )
    assert results[0].claims == []
    assert results[0].semantic_verifier is None
