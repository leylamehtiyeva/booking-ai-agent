from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.tasks.ranking_selection.dataset import load_ranking_selection_dataset
from evaluation.tasks.ranking_selection.adapter import run_selection
from evaluation.tasks.ranking_selection.comparator import compare_case
from evaluation.tasks.ranking_selection.metrics import (
    compute_group_metrics,
    compute_metrics,
)


DATASET_PATH = PROJECT_ROOT / "evaluation/datasets/ranking_selection/ranking_selection_golden_set.jsonl"
OUTPUT_PATH = PROJECT_ROOT / "evaluation/outputs/ranking_selection_eval_report.json"


def run() -> dict:
    cases = load_ranking_selection_dataset(str(DATASET_PATH))

    results = []

    for case in cases:
        predicted_items = run_selection(
            input_items=case["input_items"],
            top_n=case["top_n"],
        )

        result = compare_case(
            case=case,
            predicted_items=predicted_items,
        )

        results.append(result)

    overall_metrics = compute_metrics(results)
    group_metrics = compute_group_metrics(results)

    report = {
        "overall_metrics": overall_metrics,
        "group_metrics": group_metrics,
        "cases": results,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n=== RANKING SELECTION EVAL ===")
    print("\nOverall metrics:")
    for key, value in overall_metrics.items():
        print(f"{key}: {value}")

    print("\nGroup metrics:")
    for group, metrics in group_metrics.items():
        print(f"\n[{group}]")
        print(f"total_cases: {metrics['total_cases']}")
        print(f"exact_match_rate: {metrics['exact_match_rate']}")
        print(f"top_1_accuracy: {metrics['top_1_accuracy']}")
        print(f"ineligible_leak_rate: {metrics['ineligible_leak_rate']}")
        print(f"tier_violation_rate: {metrics['tier_violation_rate']}")

    print(f"\nSaved report to: {OUTPUT_PATH}")

    return report


if __name__ == "__main__":
    run()