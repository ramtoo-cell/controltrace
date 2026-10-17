"""Unit tests verifying ControlTrace figures, scorer separation, and minimal pairs."""

from __future__ import annotations

import unittest
from controltrace.scorer import (
    load_pilot_cases,
    load_baseline_responses,
    score_response,
    evaluate_suite,
    evaluate_minimal_pairs,
)
from controltrace.env import ControlTraceEnv


class TestControlTracePilot(unittest.TestCase):
    def test_pilot_figures_match_reported_results(self) -> None:
        """Verify that every ControlTrace figure matches the project files:
        - 6 pilot cases across 3 trap types (salience, accusation-is-not-evidence, calibrated uncertainty)
        - Outcome / conclusion accuracy: 5 of 6
        - Cited evidence that should have been excluded: 5 of 6
        - Confirmed a violation on an unsubstantiated complaint: 1 of 6 (CT-001)
        """
        report = evaluate_suite()
        self.assertEqual(report.total_cases, 6)
        self.assertEqual(report.conclusion_correct_count, 5)
        self.assertEqual(report.escalation_correct_count, 5)
        self.assertEqual(report.cited_excluded_evidence_count, 5)
        self.assertEqual(report.evidence_faithful_count, 1)
        self.assertEqual(
            report.confirmed_violation_on_unsubstantiated_complaint_count, 1
        )

    def test_ct001_vendor_disclosure_competitor_complaint_trap(self) -> None:
        """Verify CT-001 (lapsed vendor disclosure >3 years earlier + competitor complaint)."""
        cases = {c["case_id"]: c for c in load_pilot_cases()}
        responses = {
            r["case_id"]: r for r in load_baseline_responses()["responses"]
        }
        ct001_score = score_response(cases["CT-001"], responses["CT-001"])
        self.assertFalse(ct001_score.conclusion_correct)
        self.assertFalse(ct001_score.escalation_correct)
        self.assertTrue(ct001_score.cited_excluded_evidence)
        self.assertIn("E3", ct001_score.cited_excluded_ids)
        self.assertTrue(
            ct001_score.confirmed_violation_on_unsubstantiated_complaint
        )

    def test_scorer_separates_faithful_from_trapped_responses(self) -> None:
        """If the scorer cannot separate faithful from trapped responses, the scorer is presumed wrong."""
        case = load_pilot_cases()[0]
        faithful_response = {
            "case_id": case["case_id"],
            "predicted_conclusion": "no_violation",
            "predicted_escalation_action": "resolve",
            "cited_evidence_ids": ["E1", "E2"],
        }
        trapped_response = {
            "case_id": case["case_id"],
            "predicted_conclusion": "no_violation",
            "predicted_escalation_action": "resolve",
            "cited_evidence_ids": ["E1", "E2", "E3"],
        }
        s_faithful = score_response(case, faithful_response)
        s_trapped = score_response(case, trapped_response)

        self.assertTrue(s_faithful.conclusion_correct)
        self.assertTrue(s_faithful.evidence_faithful)
        self.assertFalse(s_faithful.cited_excluded_evidence)

        self.assertTrue(s_trapped.conclusion_correct)
        self.assertFalse(s_trapped.evidence_faithful)
        self.assertTrue(s_trapped.cited_excluded_evidence)

    def test_minimal_pairs_flip_between_resolve_and_escalate(self) -> None:
        """Verify minimal pairs require opposite escalation actions when one evidence item flips."""
        mp_oracle = evaluate_minimal_pairs()
        self.assertEqual(mp_oracle["total_pairs"], 2)
        self.assertEqual(mp_oracle["calibrated_pairs"], 2)

        # Verify an uncalibrated model that always escalates fails minimal-pair calibration
        always_escalate = {
            "MP-001": {"variant_resolve": "escalate", "variant_escalate": "escalate"},
            "MP-002": {"variant_resolve": "escalate", "variant_escalate": "escalate"},
        }
        mp_uncalibrated = evaluate_minimal_pairs(pair_predictions=always_escalate)
        self.assertEqual(mp_uncalibrated["calibrated_pairs"], 0)

    def test_rl_environment_reward_separation(self) -> None:
        """Verify RL environment rewards faithful investigation and penalizes unsubstantiated escalation."""
        case = load_pilot_cases()[0]
        env = ControlTraceEnv(case)
        env.step({"type": "inspect", "item_id": "E1"})
        env.step({"type": "inspect", "item_id": "E2"})
        env.step({"type": "inspect", "item_id": "E3"})
        env.step({"type": "cite", "item_id": "E1"})
        env.step({"type": "cite", "item_id": "E2"})
        env.step({"type": "exclude", "item_id": "E3"})
        _, reward_faithful, done, info = env.step(
            {
                "type": "submit",
                "conclusion": "no_violation",
                "escalation_action": "resolve",
            }
        )
        self.assertTrue(done)
        self.assertEqual(reward_faithful, 1.0)
        self.assertEqual(info["reward_components"]["faithfulness_reward"], 1.0)


if __name__ == "__main__":
    unittest.main()
