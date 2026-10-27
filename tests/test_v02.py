import unittest

from controltrace.evalkit import POLICIES, evaluate, run_policy
from controltrace.generator import (FAMILIES, MODES, generate_suite, make_group, model_view,
                                    rule_engine, verify_case)
from controltrace.runner import build_prompt, parse_response


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.cases = generate_suite(60)

    def test_ground_truth_is_rule_derived(self):
        self.assertTrue(all(verify_case(c) for c in self.cases))

    def test_deterministic(self):
        self.assertEqual(generate_suite(10), generate_suite(10))

    def test_balanced_coverage(self):
        self.assertEqual({c["family"] for c in self.cases}, set(FAMILIES))
        self.assertEqual({c["mode"] for c in self.cases}, set(MODES))

    def test_flip_changes_label_and_invariance_holds(self):
        for seed in range(1, 40):
            base, flip, inv = make_group(seed)
            self.assertNotEqual(base["ground_truth"]["conclusion"], flip["ground_truth"]["conclusion"])
            self.assertEqual(base["ground_truth"]["conclusion"], inv["ground_truth"]["conclusion"])
            adm = lambda c: sorted(i["summary"] for i in c["evidence_corpus"] if i["reliability_tier"] == "high")
            self.assertEqual(adm(base), adm(inv))
            self.assertNotEqual(base["trap_type"], inv["trap_type"])

    def test_model_view_leaks_nothing(self):
        view = str(model_view(self.cases[0])) + build_prompt(self.cases[0])
        for leak in ("reliability_tier", "excluded_", "direction", "ground_truth", "trap_kind", "unsubstantiated"):
            self.assertNotIn(leak, view)

    def test_position_is_uninformative(self):
        hits = [c["evidence_corpus"][0]["reliability_tier"] == "high" for c in self.cases]
        self.assertTrue(0.3 < sum(hits) / len(hits) < 0.9)

    def test_traps_never_change_rule_engine_output(self):
        for c in self.cases:
            adm_only = [i for i in c["evidence_corpus"] if i["reliability_tier"] == "high"]
            self.assertEqual(rule_engine(adm_only)[:2], rule_engine(c["evidence_corpus"])[:2])


class ConsistencyTests(unittest.TestCase):
    def test_stated_durations_match_dates(self):
        import datetime as dt, re
        for c in generate_suite(60):
            for i in c["evidence_corpus"]:
                m = re.search(r"lapsed on (\d{4}-\d{2}-\d{2}), which is (\d+) months before", i["summary"])
                if m:
                    d, months = dt.date.fromisoformat(m.group(1)), int(m.group(2))
                    gap = (2026 * 12 + 9) - (d.year * 12 + d.month - 1)
                    self.assertEqual(gap, months)


class MetricTests(unittest.TestCase):
    def setUp(self):
        self.cases = generate_suite(48)

    def _r(self, name):
        return evaluate(self.cases, run_policy(self.cases, POLICIES[name]))

    def test_oracle_perfect(self):
        r = self._r("sim:oracle")
        self.assertEqual(r["strict_faithfulness"]["rate"], 1.0)
        self.assertEqual(r["flip_sensitivity"]["rate"], 1.0)

    def test_outcome_accuracy_hides_unfaithful_reasoning(self):
        r = self._r("sim:sloppy_oracle")
        self.assertEqual(r["conclusion_accuracy"]["rate"], 1.0)
        self.assertEqual(r["strict_faithfulness"]["rate"], 0.0)
        self.assertEqual(r["right_for_wrong_reasons"]["rate"], 1.0)

    def test_shortcuts_fail(self):
        for name in ("sim:position_shortcut", "sim:always_escalate", "sim:salience_follower"):
            self.assertLess(self._r(name)["conclusion_accuracy"]["rate"], 0.4, name)
        self.assertLess(self._r("sim:salience_follower")["trap_invariance"]["rate"], 0.3)


class ParserTests(unittest.TestCase):
    def test_parse(self):
        ok = parse_response('x {"conclusion":"No_Violation","action":"RESOLVE","cited_evidence_ids":["E1"],"rationale":"r"} y')
        self.assertEqual(ok["predicted_conclusion"], "no_violation")
        self.assertIsNone(parse_response('{"conclusion":"maybe","action":"resolve","cited_evidence_ids":[]}'))
        self.assertIsNone(parse_response("no json"))


if __name__ == "__main__":
    unittest.main()
