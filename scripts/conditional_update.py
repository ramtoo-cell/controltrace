"""Conditional update analysis for the v0.2 transcripts.

For each (base, flip, inv) group where the model got the base case right, ask:
  - did swapping only inadmissible items (inv twin) change a correct answer?
  - did changing the decisive evidence (flip twin) produce a wrong new answer, and which one?

Usage: PYTHONPATH=src python3 scripts/conditional_update.py [--groups 40]
"""
import argparse
import collections
from pathlib import Path

from controltrace.generator import generate_suite
from controltrace.runner import responses_from_transcript


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", type=int, default=40)
    a = ap.parse_args()
    groups = {}
    for c in generate_suite(a.groups):
        groups.setdefault(c["group_id"], {})[c["role"]] = c
    tot = collections.Counter()
    for m in ("haiku", "sonnet", "opus"):
        R = responses_from_transcript(Path(f"results/v02/{m}_{a.groups}g.jsonl"))
        n = inv_bad = flip_bad = all3 = 0
        flip_said = collections.Counter()
        for g in groups.values():
            ok = {k: R.get(g[k]["case_id"], {}).get("predicted_conclusion") == g[k]["ground_truth"]["conclusion"]
                  for k in ("base", "flip", "inv")}
            all3 += all(ok.values())
            if not ok["base"]:
                continue
            n += 1
            inv_bad += not ok["inv"]
            if not ok["flip"]:
                flip_bad += 1
                flip_said[R[g["flip"]["case_id"]]["predicted_conclusion"]] += 1
        tot.update(n=n, inv_bad=inv_bad, flip_bad=flip_bad, cd=flip_said["control_deficiency"])
        print(f"{m:6s} base right {n}/{len(groups)} | inv twin changed answer {inv_bad} | "
              f"flip twin wrong {flip_bad} {dict(flip_said)} | all three right {all3}/{len(groups)}")
    print(f"TOTAL  base right {tot['n']} | inv changed {tot['inv_bad']} | flip wrong {tot['flip_bad']} "
          f"(of which control_deficiency {tot['cd']})")


if __name__ == "__main__":
    main()
