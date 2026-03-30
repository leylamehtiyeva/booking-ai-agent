import pytest

from app.logic.llm_field_fallback import classify_field_from_description
from app.schemas.fields import Field
from app.schemas.listing import ListingRaw
from app.schemas.match import Ternary


@pytest.mark.asyncio
async def test_classify_field_from_description_yes(monkeypatch):
    async def fake_to_thread(fn):
        return {"result": "YES", "reason": "Private kitchen is explicitly mentioned."}

    monkeypatch.setattr("app.logic.llm_field_fallback.asyncio.to_thread", fake_to_thread)

    listing = ListingRaw(
        id="x1",
        name="Apartment",
        description="Beautiful stay with private kitchen and balcony.",
    )

    out = await classify_field_from_description(listing, Field.KITCHEN)

    assert out.value == Ternary.YES
    assert out.evidence
    assert out.evidence[0].path == "llm_fallback"
    assert out.evidence[0].source.value == "llm"


@pytest.mark.asyncio
async def test_classify_field_from_description_no(monkeypatch):
    async def fake_to_thread(fn):
        return {"result": "NO", "reason": "Pets are not allowed."}

    monkeypatch.setattr("app.logic.llm_field_fallback.asyncio.to_thread", fake_to_thread)

    listing = ListingRaw(
        id="x2",
        name="Stay",
        description="Pets are not allowed.",
    )

    out = await classify_field_from_description(listing, Field.PET_FRIENDLY)

    assert out.value == Ternary.NO
    assert out.evidence
    assert out.evidence[0].path == "llm_fallback"
    assert out.evidence[0].source.value == "llm"


@pytest.mark.asyncio
async def test_classify_field_from_description_uncertain(monkeypatch):
    async def fake_to_thread(fn):
        return {"result": "UNCERTAIN", "reason": "No explicit evidence found."}

    monkeypatch.setattr("app.logic.llm_field_fallback.asyncio.to_thread", fake_to_thread)

    listing = ListingRaw(
        id="x3",
        name="Basic stay",
        description="Nice place in the city.",
    )

    out = await classify_field_from_description(listing, Field.OVEN)

    assert out.value == Ternary.UNCERTAIN