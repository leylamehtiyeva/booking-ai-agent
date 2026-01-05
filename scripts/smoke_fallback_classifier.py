# scripts/smoke_fallback_classifier.py
from __future__ import annotations

import json
from pathlib import Path

from app.schemas.fields import Field
from app.schemas.listing import ListingRaw
from app.logic.fallback_classifier import fallback_classify_field


def load_samples() -> list[ListingRaw]:
    p = Path("fixtures/listings_sample.json")
    data = json.loads(p.read_text(encoding="utf-8"))
    return [ListingRaw.model_validate(x) for x in data]


def main():
    listings = load_samples()
    print(f"Loaded samples: {len(listings)}")

    # Возьмем первый листинг
    lst = listings[0]

    for f in [Field.KITCHEN, Field.KETTLE, Field.PRIVATE_BATHROOM]:
        m = fallback_classify_field(lst, f)
        print(f"\nFIELD={f.name}")
        print(f"  value={m.value} conf={m.confidence}")
        if m.evidence:
            print(f"  evidence: {m.evidence[0].snippet}")


if __name__ == "__main__":
    main()
