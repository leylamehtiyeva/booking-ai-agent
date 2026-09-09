from __future__ import annotations

from app.logic.soft_evidence_routing import (
    is_controlled_structured_tag,
    resolve_deterministic_claim,
)
from app.schemas.soft_evidence import (
    ClaimResolutionMethod,
    EvidenceRelation,
    EvidenceResolutionStatus,
)


# ---------------- is_controlled_structured_tag ----------------


def test_listing_facility_name_path_is_controlled():
    assert is_controlled_structured_tag("listing.facilities[2].name") is True


def test_room_facility_name_path_is_controlled():
    assert is_controlled_structured_tag("rooms[0].facilities[1].name") is True


def test_facility_overview_path_is_not_controlled():
    assert is_controlled_structured_tag("listing.facilities[2].overview") is False


def test_room_option_choices_path_is_not_controlled():
    assert is_controlled_structured_tag("rooms[0].options[0].choices") is False


def test_room_name_path_is_not_controlled():
    assert is_controlled_structured_tag("rooms[0].name") is False


def test_description_path_is_not_controlled():
    assert is_controlled_structured_tag("listing.description") is False


def test_none_path_is_not_controlled():
    assert is_controlled_structured_tag(None) is False


# ---------------- resolve_deterministic_claim ----------------


def test_known_alias_on_controlled_tag_resolves_support():
    item = resolve_deterministic_claim(
        claim_id="RW1",
        source_type="room_facilities",
        source_path="rooms[0].facilities[3].name",
        text="Desk",
    )

    assert item is not None
    assert item.relation == EvidenceRelation.SUPPORT
    assert item.resolution_method == ClaimResolutionMethod.DETERMINISTIC
    assert item.resolution_status == EvidenceResolutionStatus.RESOLVED
    assert item.retrieval_score is None
    assert item.source_path == "rooms[0].facilities[3].name"


def test_alias_match_is_case_insensitive_and_trims_whitespace():
    item = resolve_deterministic_claim(
        claim_id="Q1",
        source_type="facilities",
        source_path="listing.facilities[0].name",
        text="  Soundproofing  ",
    )
    assert item is not None
    assert item.relation == EvidenceRelation.SUPPORT


def test_controlled_tag_with_no_known_alias_for_claim_resolves_not_enough_evidence():
    """
    A controlled structured tag whose text just doesn't match any known
    alias for this claim_id must still resolve deterministically -
    never fall through to the semantic verifier.
    """
    item = resolve_deterministic_claim(
        claim_id="RW1",
        source_type="room_facilities",
        source_path="rooms[0].facilities[3].name",
        text="Air conditioning",
    )

    assert item is not None
    assert item.relation == EvidenceRelation.NOT_ENOUGH_EVIDENCE
    assert item.resolution_method == ClaimResolutionMethod.DETERMINISTIC
    assert item.resolution_status == EvidenceResolutionStatus.RESOLVED


def test_unknown_claim_id_on_controlled_tag_resolves_not_enough_evidence():
    item = resolve_deterministic_claim(
        claim_id="BQ1",  # no alias table entry at all
        source_type="facilities",
        source_path="listing.facilities[0].name",
        text="Free WiFi",
    )
    assert item is not None
    assert item.relation == EvidenceRelation.NOT_ENOUGH_EVIDENCE


def test_non_controlled_path_returns_none():
    item = resolve_deterministic_claim(
        claim_id="RW1",
        source_type="room_facilities",
        source_path="rooms[0].facilities[3].overview",
        text="Desk",
    )
    assert item is None


def test_non_structured_source_type_returns_none():
    item = resolve_deterministic_claim(
        claim_id="Q1",
        source_type="description",
        source_path="listing.description",
        text="Soundproofing",
    )
    assert item is None
