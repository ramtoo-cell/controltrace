"""Three-axis deterministic scorer for ControlTrace (PCAOB AS 1105 / ISA 500).

Scores three dimensions separately without collapsing them into a composite metric:
1. Conclusion Accuracy: Did the agent reach the ground-truth substantive determination?
2. Evidence Faithfulness: Did the agent cite all required admissible evidence and avoid
   citing excluded evidence (uncorroborated allegations, red herrings, informal assertions)?
3. Escalation Calibration: Did the agent choose the right operational action (resolve vs. escalate)?
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    trap_type: str
    conclusion_correct: bool
    escalation_correct: bool
    cited_excluded_evidence: bool
    evidence_faithful: bool
    required_evidence_coverage: float
    cited_excluded_ids: List[str]
    missing_required_ids: List[str]
    confirmed_violation_on_unsubstantiated_complaint: bool


@dataclass(frozen=True)
class SuiteReport:
    benchmark: str
    model_evaluated: str
    total_cases: int
    conclusion_correct_count: int
    escalation_correct_count: int
    cited_excluded_evidence_count: int
    evidence_faithful_count: int
    confirmed_violation_on_unsubstantiated_complaint_count: int
    case_scores: List[CaseScore]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "benchmark": self.benchmark,
            "model_evaluated": self.model_evaluated,
            "total_cases": self.total_cases,
            "conclusion_correct_count": self.conclusion_correct_count,
            "escalation_correct_count": self.escalation_correct_count,
            "cited_excluded_evidence_count": self.cited_excluded_evidence_count,
            "evidence_faithful_count": self.evidence_faithful_count,
            "confirmed_violation_on_unsubstantiated_complaint_count": (
                self.confirmed_violation_on_unsubstantiated_complaint_count
            ),
            "summary_fractions": {
                "conclusion_accuracy": f"{self.conclusion_correct_count}/{self.total_cases}",
                "escalation_accuracy": f"{self.escalation_correct_count}/{self.total_cases}",
                "cited_excluded_evidence": f"{self.cited_excluded_evidence_count}/{self.total_cases}",
                "strictly_faithful_evidence": f"{self.evidence_faithful_count}/{self.total_cases}",
                "unsubstantiated_complaint_false_escalation": (
                    f"{self.confirmed_violation_on_unsubstantiated_complaint_count}/{self.total_cases}"
                ),
            },
            "case_scores": [asdict(score) for score in self.case_scores],
        }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_pilot_cases(path: Path | None = None) -> List[Dict[str, Any]]:
    target = path or (_repo_root() / "data" / "pilot_cases_public.json")
    with target.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_baseline_responses(path: Path | None = None) -> Dict[str, Any]:
    target = path or (_repo_root() / "results" / "claude_blind_baseline_6cases.json")
    with target.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_minimal_pairs(path: Path | None = None) -> List[Dict[str, Any]]:
    target = path or (_repo_root() / "data" / "minimal_pairs_public.json")
    with target.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def score_response(case: Dict[str, Any], response: Dict[str, Any]) -> CaseScore:
    gt = case["ground_truth"]
    cited_set = set(response.get("cited_evidence_ids", []))
    required_set = set(gt["required_evidence_ids"])
    excluded_set = set(gt["excluded_evidence_ids"])

    cited_excluded_ids = sorted(cited_set.intersection(excluded_set))
    missing_required_ids = sorted(required_set.difference(cited_set))

    conclusion_correct = response.get("predicted_conclusion") == gt["conclusion"]
    escalation_correct = response.get("predicted_escalation_action") == gt["escalation_action"]
    cited_excluded_evidence = len(cited_excluded_ids) > 0
    required_coverage = (
        len(required_set.intersection(cited_set)) / len(required_set)
        if required_set
        else 1.0
    )
    evidence_faithful = (not cited_excluded_evidence) and (len(missing_required_ids) == 0)

    uncorroborated_ids = {
        item["item_id"]
        for item in case.get("evidence_corpus", [])
        if "uncorroborated" in item.get("source_type", "")
        or "unsubstantiated" in item.get("reliability_tier", "")
    }
    confirmed_on_unsubstantiated = (
        not conclusion_correct
        and response.get("predicted_conclusion") == "violation_confirmed"
        and response.get("predicted_escalation_action") == "escalate"
        and bool(cited_set.intersection(uncorroborated_ids))
    )

    return CaseScore(
        case_id=case["case_id"],
        trap_type=case["trap_type"],
        conclusion_correct=conclusion_correct,
        escalation_correct=escalation_correct,
        cited_excluded_evidence=cited_excluded_evidence,
        evidence_faithful=evidence_faithful,
        required_evidence_coverage=round(required_coverage, 4),
        cited_excluded_ids=cited_excluded_ids,
        missing_required_ids=missing_required_ids,
        confirmed_violation_on_unsubstantiated_complaint=confirmed_on_unsubstantiated,
    )


def evaluate_suite(
    cases: List[Dict[str, Any]] | None = None,
    baseline_payload: Dict[str, Any] | None = None,
) -> SuiteReport:
    cases_list = cases if cases is not None else load_pilot_cases()
    payload = baseline_payload if baseline_payload is not None else load_baseline_responses()
    responses_by_id = {r["case_id"]: r for r in payload.get("responses", [])}

    scores: List[CaseScore] = []
    for case in cases_list:
        cid = case["case_id"]
        if cid not in responses_by_id:
            raise KeyError(f"Missing response for case_id={cid}")
        scores.append(score_response(case, responses_by_id[cid]))

    return SuiteReport(
        benchmark=payload.get("benchmark", "ControlTrace"),
        model_evaluated=payload.get("model_evaluated", "unknown"),
        total_cases=len(scores),
        conclusion_correct_count=sum(1 for s in scores if s.conclusion_correct),
        escalation_correct_count=sum(1 for s in scores if s.escalation_correct),
        cited_excluded_evidence_count=sum(1 for s in scores if s.cited_excluded_evidence),
        evidence_faithful_count=sum(1 for s in scores if s.evidence_faithful),
        confirmed_violation_on_unsubstantiated_complaint_count=sum(
            1 for s in scores if s.confirmed_violation_on_unsubstantiated_complaint
        ),
        case_scores=scores,
    )


def evaluate_minimal_pairs(
    pairs: List[Dict[str, Any]] | None = None,
    pair_predictions: Dict[str, Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    """Evaluate minimal-pair escalation calibration.

    Each pair consists of two variants (resolve vs. escalate) differing by a single piece
    of evidence. A pair is scored as calibrated only if the model resolves variant_resolve
    and escalates variant_escalate.
    """
    pairs_list = pairs if pairs is not None else load_minimal_pairs()
    if pair_predictions is None:
        # Canonical oracle sanity check when no external predictions are supplied
        pair_predictions = {
            p["pair_id"]: {
                "variant_resolve": p["variant_resolve"]["expected_escalation_action"],
                "variant_escalate": p["variant_escalate"]["expected_escalation_action"],
            }
            for p in pairs_list
        }

    results = []
    for pair in pairs_list:
        pid = pair["pair_id"]
        preds = pair_predictions.get(pid, {})
        resolve_ok = (
            preds.get("variant_resolve")
            == pair["variant_resolve"]["expected_escalation_action"]
        )
        escalate_ok = (
            preds.get("variant_escalate")
            == pair["variant_escalate"]["expected_escalation_action"]
        )
        results.append(
            {
                "pair_id": pid,
                "title": pair["title"],
                "resolve_variant_correct": resolve_ok,
                "escalate_variant_correct": escalate_ok,
                "pair_flip_calibrated": resolve_ok and escalate_ok,
            }
        )

    calibrated_count = sum(1 for r in results if r["pair_flip_calibrated"])
    return {
        "total_pairs": len(results),
        "calibrated_pairs": calibrated_count,
        "pair_results": results,
    }
