from app.logic.unknown_field_evidence_search import (
    UnknownFieldEvidence,
    UnknownFieldSearchResult,
    _normalize_unknown_field_result,
)


def test_unknown_field_not_found_without_evidence_becomes_uncertain():
    result = UnknownFieldSearchResult(
        query_text="satellite TV",
        value="NOT_FOUND",
        reason="Satellite TV is not mentioned in the listing.",
        evidence=[],
    )

    normalized = _normalize_unknown_field_result(result)

    assert normalized.value == "UNCERTAIN"
    assert normalized.reason == "satellite TV is not explicitly mentioned in the listing."
    assert normalized.evidence == []


def test_unknown_field_not_found_with_negative_evidence_stays_not_found():
    result = UnknownFieldSearchResult(
        query_text="satellite TV",
        value="NOT_FOUND",
        reason="Satellite TV is explicitly unavailable in the listing.",
        evidence=[
            UnknownFieldEvidence(
                source_path="listing.description",
                snippet="No satellite channels available.",
            )
        ],
    )

    normalized = _normalize_unknown_field_result(result)

    assert normalized.value == "NOT_FOUND"
    assert normalized.reason == "Satellite TV is explicitly unavailable in the listing."
    assert len(normalized.evidence) == 1


def test_unknown_field_found_stays_found():
    result = UnknownFieldSearchResult(
        query_text="satellite TV",
        value="FOUND",
        reason="Satellite TV is explicitly mentioned in the listing.",
        evidence=[
            UnknownFieldEvidence(
                source_path="rooms[0].facilities",
                snippet="Satellite channels",
            )
        ],
    )

    normalized = _normalize_unknown_field_result(result)

    assert normalized.value == "FOUND"
    assert normalized.reason == "Satellite TV is explicitly mentioned in the listing."
    assert len(normalized.evidence) == 1
    
    
    def test_satellite_tv_detected_from_satellite_channels():
        signals = [
            {"path": "listing.facilities", "text": "Satellite channels"}
        ]

        result = asyncio.run(
            search_unknown_must_have_evidence(
                query_text="satellite TV",
                listing_signals=signals,
            )
        )

        assert result.value == "FOUND"