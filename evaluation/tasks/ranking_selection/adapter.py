from app.logic.result_selection import classify_ranked_item, select_ranked_items


def run_selection(input_items: list[dict], top_n: int) -> list[dict]:
    return select_ranked_items(input_items, top_n=top_n)


def classify_all_items(input_items: list[dict]) -> list[dict]:
    return [classify_ranked_item(item) for item in input_items]