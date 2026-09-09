"""
Strict source-aware routing for the new soft-preference evidence
pipeline.

Deliberately separate from app.logic.field_rules / matcher_structured
(the existing production deterministic matcher): per the approved
migration design, this is a new, stricter routing layer based on the
experimentally validated controlled-structured-path check
(evaluation/experiments/pipeline_cleanup_v2/structured_tag_rule.py) and
alias table (.../deterministic_mapping.py), not a tightening of the
existing field_rules.py behavior. Reconciling the two is explicitly a
later step, after shadow-mode comparison.

A path counts as a controlled structured tag only if it is exactly
Facility.name at the listing level or the room level:
    listing.facilities[N].name
    rooms[N].facilities[M].name
Everything else (.overview prose, rooms[N].options[M].choices,
rooms[N].name, highlights, description, policies, fine_print) is free
text and must go through the semantic verifier instead.
"""

from __future__ import annotations

import re

from app.schemas.soft_evidence import (
    ClaimResolutionMethod,
    EvidenceItem,
    EvidenceRelation,
    EvidenceResolutionStatus,
)

STRUCTURED_SOURCE_TYPES = {"facilities", "room_facilities"}

_FACILITY_NAME_PATTERN = re.compile(
    r"^(listing\.facilities\[\d+\]|rooms\[\d+\]\.facilities\[\d+\])\.name$"
)

# Only the claim IDs already experimentally validated against the frozen
# held-out benchmark (evaluation/experiments/pipeline_cleanup_v2/
# deterministic_mapping.py::DETERMINISTIC_ALIASES). Deliberately
# incomplete - Phase B's atomic decomposition step will extend this as
# new claim IDs are defined per constraint category. Do not add guessed
# entries here.
#
# FC2 intentionally excluded (Phase B correction): it belongs to an
# earlier, superseded family-friendly decomposition
# (retrieval_checkpoint_v2.jsonl / build_input_v2.py, oracle-NLI-only
# validated) that never went through the frozen A1/A2/B/C verifier
# comparison and is not one of the 12 claim IDs Phase B's atomic
# decomposition (app.logic.soft_preference_decomposition) produces -
# this alias entry was unreachable dead code. Not reinstated here; a
# possible later, explicit extension alongside FC3.
DETERMINISTIC_CLAIM_ALIASES: dict[str, set[str]] = {
    "RW1": {"desk"},
    "RW2A": {"free wifi"},
    "Q1": {"soundproofing", "soundproof rooms"},
}


def is_controlled_structured_tag(path: str | None) -> bool:
    if not path:
        return False
    return bool(_FACILITY_NAME_PATTERN.match(path))


def resolve_deterministic_claim(
    *,
    claim_id: str,
    source_type: str,
    source_path: str | None,
    text: str,
) -> EvidenceItem | None:
    """
    Returns:
    - None: not a controlled structured tag -> genuine free text, the
      caller should route this candidate to the semantic verifier
      instead.
    - EvidenceItem(relation=SUPPORT): controlled tag with a known alias
      match for this claim_id.
    - EvidenceItem(relation=NOT_ENOUGH_EVIDENCE): controlled tag, but no
      known mapping exists for this claim_id -> deliberately resolved
      deterministically as "no evidence" and NEVER forwarded to the
      semantic verifier (a raw structured tag string is not
      natural-language evidence to reason over).
    """
    if source_type not in STRUCTURED_SOURCE_TYPES:
        return None
    if not is_controlled_structured_tag(source_path):
        return None

    aliases = DETERMINISTIC_CLAIM_ALIASES.get(claim_id, set())
    matched = text.strip().casefold() in aliases

    return EvidenceItem(
        evidence_text=text,
        relation=EvidenceRelation.SUPPORT if matched else EvidenceRelation.NOT_ENOUGH_EVIDENCE,
        resolution_method=ClaimResolutionMethod.DETERMINISTIC,
        resolution_status=EvidenceResolutionStatus.RESOLVED,
        source_type=source_type,
        source_path=source_path,
        retrieval_score=None,
    )
