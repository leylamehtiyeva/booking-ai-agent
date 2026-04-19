from __future__ import annotations


def safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def _compute_group_metrics(case_results: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}

    for row in case_results:
        group = row.get("group", "unknown")
        grouped.setdefault(group, []).append(row)

    out = []
    for group, rows in sorted(grouped.items()):
        total_gold = 0
        total_pred = 0
        total_correct = 0

        total_priority = 0
        total_priority_correct = 0

        total_category = 0
        total_category_correct = 0

        total_mapping_status = 0
        total_mapping_status_correct = 0

        total_mapped_fields = 0
        total_mapped_fields_correct = 0

        total_evidence_strategy = 0
        total_evidence_strategy_correct = 0

        exact_constraint_set_match_cases = 0
        exact_full_case_match_cases = 0
        no_constraint_cases = 0

        for row in rows:
            ce = row["constraint_extraction"]
            total_gold += ce["gold_count"]
            total_pred += ce["pred_count"]
            total_correct += ce["correct_count"]

            if ce["gold_count"] == 0:
                no_constraint_cases += 1

            if ce["exact_constraint_set_match"]:
                exact_constraint_set_match_cases += 1

            if ce["exact_full_case_match"]:
                exact_full_case_match_cases += 1

            for m in row["matched_rows"]:
                total_priority += 1
                total_category += 1
                total_mapping_status += 1
                total_mapped_fields += 1
                total_evidence_strategy += 1

                if m["priority_correct"]:
                    total_priority_correct += 1
                if m["category_correct"]:
                    total_category_correct += 1
                if m["mapping_status_correct"]:
                    total_mapping_status_correct += 1
                if m["mapped_fields_exact_match"]:
                    total_mapped_fields_correct += 1
                if m["evidence_strategy_correct"]:
                    total_evidence_strategy_correct += 1

        if total_gold == 0 and total_pred == 0:
            precision = 1.0
            recall = 1.0
            f1 = 1.0
        else:
            precision = safe_div(total_correct, total_pred)
            recall = safe_div(total_correct, total_gold)
            f1 = safe_div(2 * precision * recall, precision + recall)

        out.append(
            {
                "group": group,
                "cases": len(rows),
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "priority_acc": safe_div(total_priority_correct, total_priority),
                "category_acc": safe_div(total_category_correct, total_category),
                "mapping_status_acc": safe_div(total_mapping_status_correct, total_mapping_status),
                "mapped_fields_exact_match_acc": safe_div(total_mapped_fields_correct, total_mapped_fields),
                "evidence_strategy_acc": safe_div(total_evidence_strategy_correct, total_evidence_strategy),
                "exact_constraint_set_match_rate": safe_div(exact_constraint_set_match_cases, len(rows)),
                "exact_full_case_match_rate": safe_div(exact_full_case_match_cases, len(rows)),
                "no_constraint_case_rate": safe_div(no_constraint_cases, len(rows)),
            }
        )

    return out


def compute_metrics(case_results: list[dict]) -> dict:
    total_gold = 0
    total_pred = 0
    total_correct = 0

    total_priority = 0
    total_priority_correct = 0

    total_category = 0
    total_category_correct = 0

    total_mapping_status = 0
    total_mapping_status_correct = 0

    total_mapped_fields = 0
    total_mapped_fields_correct = 0

    total_evidence_strategy = 0
    total_evidence_strategy_correct = 0

    exact_constraint_set_match_cases = 0
    exact_full_case_match_cases = 0
    no_constraint_cases = 0

    for row in case_results:
        ce = row["constraint_extraction"]
        total_gold += ce["gold_count"]
        total_pred += ce["pred_count"]
        total_correct += ce["correct_count"]

        if ce["gold_count"] == 0:
            no_constraint_cases += 1

        if ce["exact_constraint_set_match"]:
            exact_constraint_set_match_cases += 1

        if ce["exact_full_case_match"]:
            exact_full_case_match_cases += 1

        for m in row["matched_rows"]:
            total_priority += 1
            total_category += 1
            total_mapping_status += 1
            total_mapped_fields += 1
            total_evidence_strategy += 1

            if m["priority_correct"]:
                total_priority_correct += 1
            if m["category_correct"]:
                total_category_correct += 1
            if m["mapping_status_correct"]:
                total_mapping_status_correct += 1
            if m["mapped_fields_exact_match"]:
                total_mapped_fields_correct += 1
            if m["evidence_strategy_correct"]:
                total_evidence_strategy_correct += 1

    if total_gold == 0 and total_pred == 0:
        precision = 1.0
        recall = 1.0
        f1 = 1.0
    else:
        precision = safe_div(total_correct, total_pred)
        recall = safe_div(total_correct, total_gold)
        f1 = safe_div(2 * precision * recall, precision + recall)

    return {
        "constraint_extraction_precision": precision,
        "constraint_extraction_recall": recall,
        "constraint_extraction_f1": f1,
        "priority_accuracy_on_matched_constraints": safe_div(total_priority_correct, total_priority),
        "category_accuracy_on_matched_constraints": safe_div(total_category_correct, total_category),
        "mapping_status_accuracy_on_matched_constraints": safe_div(
            total_mapping_status_correct, total_mapping_status
        ),
        "mapped_fields_exact_match_accuracy_on_matched_constraints": safe_div(
            total_mapped_fields_correct, total_mapped_fields
        ),
        "evidence_strategy_accuracy_on_matched_constraints": safe_div(
            total_evidence_strategy_correct, total_evidence_strategy
        ),
        "exact_constraint_set_match_rate": safe_div(exact_constraint_set_match_cases, len(case_results)),
        "exact_full_case_match_rate": safe_div(exact_full_case_match_cases, len(case_results)),
        "no_constraint_case_rate": safe_div(no_constraint_cases, len(case_results)),
        "counts": {
            "n_cases": len(case_results),
            "total_gold_constraints": total_gold,
            "total_pred_constraints": total_pred,
            "total_correct_constraints": total_correct,
            "total_priority_rows": total_priority,
            "total_priority_correct": total_priority_correct,
            "total_category_rows": total_category,
            "total_category_correct": total_category_correct,
            "total_mapping_status_rows": total_mapping_status,
            "total_mapping_status_correct": total_mapping_status_correct,
            "total_mapped_fields_rows": total_mapped_fields,
            "total_mapped_fields_correct": total_mapped_fields_correct,
            "total_evidence_strategy_rows": total_evidence_strategy,
            "total_evidence_strategy_correct": total_evidence_strategy_correct,
            "exact_constraint_set_match_cases": exact_constraint_set_match_cases,
            "exact_full_case_match_cases": exact_full_case_match_cases,
            "no_constraint_cases": no_constraint_cases,
        },
        "group_breakdown": _compute_group_metrics(case_results),
    }