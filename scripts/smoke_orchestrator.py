import asyncio

from app.orchestrator.orchestrator import run_orchestrator


def main():
    user_text = "Хочу квартиру в Баку с возможностью готовить еду, чайником и ванной"
    resp = asyncio.run(run_orchestrator(user_text, top_n=3, fallback_top_k=3, listings_source="fixtures"))

    print("SUMMARY:", resp.request_summary)
    for i, r in enumerate(resp.results, 1):
        print(f"\n{i}. {r.listing.name} | score={r.score:.1f} | must={r.must_have_matched}/{r.must_have_total}")
        for w in r.why[:6]:
            print("   -", w)


if __name__ == "__main__":
    main()
