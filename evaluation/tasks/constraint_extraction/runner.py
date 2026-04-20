from __future__ import annotations

import asyncio

from evaluation.core.io import load_jsonl, save_json
from evaluation.tasks.constraint_extraction.dataset import ConstraintEvalCase
from evaluation.tasks.constraint_extraction.adapter import run_case
from evaluation.tasks.constraint_extraction.comparator import compare_case
from evaluation.tasks.constraint_extraction.metrics import compute_metrics


async def run_eval(dataset_path: str, output_path: str) -> dict:
    raw_cases = load_jsonl(dataset_path)
    cases = [ConstraintEvalCase.model_validate(x) for x in raw_cases]

    case_results = []

    for case in cases:
        try:
            result = await run_case(case.user_message)
            compared = compare_case(case, result)
            case_results.append(compared)
        except Exception as e:
            case_results.append(
                {
                    "case_id": case.case_id,
                    "group": case.group,
                    "user_message": case.user_message,
                    "error": str(e),
                    "constraint_extraction": {
                        "gold_count": len(case.expected_constraints),
                        "pred_count": 0,
                        "correct_count": 0,
                        "missed_constraints": [c.normalized_text for c in case.expected_constraints],
                        "extra_constraints": [],
                        "exact_constraint_set_match": False,
                        "exact_full_case_match": False,
                    },
                    "matched_rows": [],
                }
            )

    metrics = compute_metrics(case_results)

    report = {
        "dataset_path": dataset_path,
        "n_cases": len(cases),
        "metrics": metrics,
        "cases": case_results,
    }

    save_json(output_path, report)
    return report


if __name__ == "__main__":
    dataset_path = "evaluation/datasets/constraint_extraction/constraint_golden_set_v2_final.jsonl"
    output_path = "evaluation/outputs/constraint_extraction_report.json"
    asyncio.run(run_eval(dataset_path, output_path))