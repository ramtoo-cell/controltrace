# ControlTrace v0.2 — procedural generation, counterfactual twins, live-model results

Everything below is reproducible from the raw transcripts in `results/v02/*.jsonl` (full prompt, full raw
model output, per-call latency). Nothing is hand-labelled: ground truth is derived by a rule engine
(`src/controltrace/generator.py::rule_engine`) from hidden evidence metadata.

## What changed from v0.1

| | v0.1 pilot | v0.2 |
|:--|:--|:--|
| Cases | 6 hand-written | procedural; 6 policy families x 4 outcomes x 6 trap types; 120 evaluated here (360 generated per 120 groups, unlimited) |
| Ground truth | single author | derived by rule engine; `tests/test_v02.py` checks every case |
| Item order | decisive evidence always E1/E2 | shuffled; a position-shortcut policy scores 29% |
| Model sees | corpus incl. `reliability_tier` labels (possible leak) | summaries only; a test asserts no tier/direction/trap label reaches the prompt |
| Causal test | 2 hand-built minimal pairs | every case has a **flip twin** (admissible evidence changes, label must change) and an **invariance twin** (only inadmissible traps change, label must not) |
| Baseline | one transcript, one sample | 360 live calls, raw transcripts saved, resumable runner, Wilson 95% CIs |

## Metrics

* **Conclusion accuracy / Faithful citations** — as v0.1 (cites all admissible items, none excluded).
* **Right for wrong reasons** — correct conclusion *and* unfaithful citations: what outcome-only scoring cannot see.
* **Flip sensitivity** — per group: correct on *both* the base case and its flip twin (did the model update when the decisive evidence changed?).
* **Trap invariance** — per group: same, correct conclusion on base and invariance twin (did junk change its mind?).

## Results (40 groups = 120 cases, 1 sample/case, 95% Wilson CI)

| Agent | Conclusion acc. | Faithful citations | Right for wrong reasons | Flip sensitivity | Trap invariance |
|:--|:--|:--|:--|:--|:--|
| Claude Haiku | 82% (74-88) | 82% (75-88) | 11% (6-18) | 57% (42-71) | 80% (65-90) |
| Claude Sonnet | 86% (78-91) | 88% (80-92) | 11% (6-18) | 75% (60-86) | 78% (62-88) |
| Claude Opus | 92% (86-96) | 100% (97-100) | 0% (0-3) | 82% (68-91) | 90% (77-96) |

Models were called through the `claude` CLI aliases `haiku`, `sonnet`, `opus` (tools disabled, empty working
directory, custom system prompt) on 2026-10-20; the alias resolves to whatever model Anthropic serves under that
name on that date. 13 Sonnet outputs closed the JSON with a typographic quote; they are recovered by a lenient
field extractor applied identically to all models and flagged `parse_mode: lenient` in the data.

### Reference policies (simulated, NOT models) — does the benchmark separate failure modes?

| Policy | Conclusion acc. | Faithful | Right for wrong reasons | Flip | Invariance |
|:--|:--|:--|:--|:--|:--|
| oracle | 100% | 100% | 0% | 100% | 100% |
| right answer, cites everything | 100% | 0% | **100%** | 100% | 100% |
| always escalate | 24% | 0% | 24% | 0% | 25% |
| believes any adverse allegation | 34% | 16% | 18% | 10% | 25% |
| follows the loudest trap | 29% | 7% | 22% | 10% | 10% |
| "E1/E2 are the real evidence" | 29% | 11% | 26% | 0% | 30% |

The second row is the point of the project: identical to the oracle on every outcome metric, 0% on faithfulness.

## What the data says (and does not)

1. **The v0.1 headline does not replicate.** v0.1 reported Claude treating an unsubstantiated competitor
   complaint as proof (1/6). Here, false confirmation on an unsubstantiated allegation was **0/120 for all three
   models**, and Opus cited no excluded evidence at all. v0.1's 5/6 "cited excluded evidence" was on 6 cases of
   a different construction and should not be cited as a general finding.
2. **Failure direction differs by model size.** Haiku mostly *under-calls* severity (14 under- vs 8 over-calls:
   e.g. `violation_confirmed -> control_deficiency`, `insufficient_evidence -> control_deficiency`), Sonnet
   leans to over-calls (11 vs 5), and every one of Opus's 9 conclusion errors is an over-call (e.g. a
   compliant case called a deficiency). Flip sensitivity (57-82%) is below trap invariance for all three
   models: updating correctly when the decisive evidence changes is harder than ignoring junk.
3. **Unfaithful citations are mostly *missing* required evidence, and sometimes citing excluded items.**
   Citing an inadmissible item: Haiku 6/120 (5%), Sonnet 11/120 (9%), Opus 0/120. Total unfaithful cases are
   Haiku 21, Sonnet 15, Opus 0, so the rest of the unfaithful cases only *omitted* a required admissible item. About 11% of Haiku and
   Sonnet cases reached the right conclusion with an unfaithful evidence trail; Opus 0%. Outcome accuracy
   alone (82/86/92%) hides this.
4. **Conditional on a correct base answer, junk almost never moves the model; decisive evidence often moves it
   to the wrong place.** Across the 100 groups (all models) where the base case was answered correctly, the
   invariance twin changed the answer once (1/100), while the flip twin got a wrong new conclusion 14 times
   (14/100). 11 of those 14 landed on the middle category `control_deficiency` rather than the conclusion the
   new evidence supported. Haiku accounts for 9 of the 14 (Sonnet 2, Opus 3), and with one sample per case
   this is a pattern to test at k >= 5, not a settled effect. Reproduce:
   `PYTHONPATH=src python3 scripts/conditional_update.py`.

## Limitations (stated plainly)

* **N=120 cases / 40 groups, one sample each.** CIs are wide; differences between adjacent models are not all
  significant (Haiku vs Sonnet overlap on almost every metric). No pass@k or temperature study yet.
* **Synthetic and template-based.** Phrasing variety is limited (6 families, ~3 paraphrases per slot); a model
  could in principle learn the templates. Held-out families are the next step.
* **Label boundary.** `control_deficiency` vs `violation_confirmed` depends on a definition supplied in the
  prompt ("independent evidence of actual misuse, loss or harm"); some residual errors are boundary disagreements,
  not reasoning failures. Preliminary runs without that definition were discarded
  (`results/_archive_invalid_prelim/`).
* **Ground truth is rule-derived, not expert-validated.** The rule encodes one reading of AS 1105 / ISA 500.
  Independent blind labelling by practising auditors (inter-rater kappa) is still outstanding and is the single
  most valuable next step.
* **Model identity.** CLI aliases, not pinned snapshot IDs.
* **Harness differences.** Calls go through Claude Code's CLI with tools disabled, not the raw Messages API.

## Reproduce

```bash
PYTHONPATH=src python3 -m unittest discover -s tests          # 16 tests
PYTHONPATH=src python3 -m controltrace.cli2 sim --groups 40    # simulated reference policies
PYTHONPATH=src python3 -m controltrace.cli2 report results/v02/opus_40g.jsonl --groups 40   # rescore saved transcript
PYTHONPATH=src python3 -m controltrace.cli2 run --model opus --groups 40                     # live (needs `claude` CLI)
```
