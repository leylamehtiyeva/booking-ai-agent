from dotenv import load_dotenv
load_dotenv()

from app.logic.intent_router import build_search_request_adk


def main() -> None:
    text = "Хочу квартиру в Баку с возможностью готовить еду, чайником и ванной"
    req = build_search_request_adk(text)
    print(req.model_dump())

if __name__ == "__main__":
    main()
