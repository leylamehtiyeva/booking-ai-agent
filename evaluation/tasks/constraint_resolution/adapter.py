from __future__ import annotations

from typing import Any

from app.logic.constraint_evidence_resolution import (
    ConstraintResolutionRequest,
    resolve_constraint_via_textual_evidence,
)

from evaluation.tasks.constraint_resolution.dataset import ConstraintResolutionEvalCase


async def run_case(case: ConstraintResolutionEvalCase) -> dict[str, Any]:
    constraint = case.constraint

    req = ConstraintResolutionRequest(
        listing_id=case.case_id,
        listing_title=None,
        constraint_id=case.case_id,
        raw_text=constraint.raw_text,
        normalized_text=constraint.normalized_text,
        priority=constraint.priority,
        category=constraint.category,
        mapping_status=constraint.mapping_status,
        evidence_strategy=constraint.evidence_strategy,
        mapped_fields=constraint.mapped_fields,
        structured_value=constraint.structured_value,
        resolver_type="textual",
        listing_evidence=[
            {
                "source": evidence.source,
                "path": evidence.path or "",
                "text": evidence.text,
            }
            for evidence in case.listing_evidence
        ],
    )

    result = await resolve_constraint_via_textual_evidence(req)

    return result.model_dump(mode="json")