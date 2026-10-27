"""ControlTrace v0.2 command line: generate / sim / run / report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evalkit import POLICIES, evaluate, run_policy
from .generator import generate_suite
from .runner import responses_from_transcript, run_cases


def _fmt(r: dict) -> str:
    rows = ["conclusion_accuracy", "escalation_accuracy", "strict_faithfulness", "right_for_wrong_reasons",
            "flip_sensitivity", "trap_invariance", "trap_swing"]
    return "\n".join(f"  {k:26} {r[k]['k']:>4}/{r[k]['n']:<4} {r[k]['rate']:.1%}  95% CI {r[k]['ci95'][0]:.1%}-{r[k]['ci95'][1]:.1%}"
                     for k in rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="controltrace2")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate"); g.add_argument("--groups", type=int, default=120); g.add_argument("--out", default="data/v02_suite.json")
    sub.add_parser("sim").add_argument("--groups", type=int, default=120)
    r = sub.add_parser("run"); r.add_argument("--model", required=True); r.add_argument("--groups", type=int, default=40)
    r.add_argument("--samples", type=int, default=1); r.add_argument("--workers", type=int, default=6)
    r.add_argument("--transcript", default=None)
    p = sub.add_parser("report"); p.add_argument("transcript"); p.add_argument("--groups", type=int, default=40)
    a = ap.parse_args(argv)

    if a.cmd == "generate":
        Path(a.out).write_text(json.dumps(generate_suite(a.groups), indent=1)); print(f"wrote {a.out}")
    elif a.cmd == "sim":
        cs = generate_suite(a.groups)
        for name, pol in POLICIES.items():
            print(name); print(_fmt(evaluate(cs, run_policy(cs, pol))))
    elif a.cmd == "run":
        cs = generate_suite(a.groups)
        t = Path(a.transcript or f"results/v02/{a.model}_{a.groups}g.jsonl")
        run_cases(cs, a.model, t, a.samples, a.workers)
        print(_fmt(evaluate(cs, responses_from_transcript(t))))
    elif a.cmd == "report":
        cs = generate_suite(a.groups)
        print(_fmt(evaluate(cs, responses_from_transcript(Path(a.transcript)))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
