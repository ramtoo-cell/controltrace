"""Command-line interface for running and verifying ControlTrace pilot evaluations."""

from __future__ import annotations

import argparse
import json
from .scorer import evaluate_suite, evaluate_minimal_pairs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ControlTrace: Audit-Evidence Faithfulness & Calibrated Escalation Benchmark (PCAOB AS 1105 / ISA 500)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit full JSON evaluation report",
    )
    args = parser.parse_args()

    report = evaluate_suite()
    mp_report = evaluate_minimal_pairs()

    if args.json:
        print(
            json.dumps(
                {
                    "pilot_evaluation": report.to_dict(),
                    "minimal_pairs_schema_check": mp_report,
                },
                indent=2,
            )
        )
        return

    print("=" * 78)
    print("ControlTrace (v0.1.0-pilot) — PCAOB AS 1105 / ISA 500 Evaluation Report")
    print("=" * 78)
    print(f"Model Evaluated : {report.model_evaluated} (blind subagent, 1 sample/case)")
    print(f"Total Cases     : {report.total_cases}")
    print("-" * 78)
    print(
        f"1. Conclusion Accuracy                     : {report.conclusion_correct_count}/{report.total_cases}"
    )
    print(
        f"2. Cited Excluded Evidence (Unfaithful)    : {report.cited_excluded_evidence_count}/{report.total_cases}"
    )
    print(
        f"   Strictly Faithful Evidence Citations    : {report.evidence_faithful_count}/{report.total_cases}"
    )
    print(
        f"3. Escalation Action Accuracy              : {report.escalation_correct_count}/{report.total_cases}"
    )
    print(
        f"   False Violation on Unsubstantiated Claim: {report.confirmed_violation_on_unsubstantiated_complaint_count}/{report.total_cases}"
    )
    print("-" * 78)
    print(
        f"{'Case':<8} {'Trap Type':<28} {'Conclusion':<12} {'Escalation':<12} {'Cited Excluded'}"
    )
    print("-" * 78)
    for score in report.case_scores:
        excl_str = (
            f"YES ({','.join(score.cited_excluded_ids)})"
            if score.cited_excluded_evidence
            else "NO (Clean)"
        )
        print(
            f"{score.case_id:<8} {score.trap_type:<28} "
            f"{'PASS' if score.conclusion_correct else 'FAIL':<12} "
            f"{'PASS' if score.escalation_correct else 'FAIL':<12} "
            f"{excl_str}"
        )
    print("=" * 78)


if __name__ == "__main__":
    main()
