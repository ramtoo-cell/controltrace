# ControlTrace: Teaching AI Agents the Difference Between Allegation and Proof

**Evaluating AI Judgment, Evidence Sufficiency, and Calibrated Escalation Under Codified Audit Standards (PCAOB AS 1105 & ISA 500)**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-1f6feb?style=flat-square)](https://www.python.org/)
[![Standards](https://img.shields.io/badge/Rubric_Anchor-PCAOB_AS_1105_%7C_ISA_500-0969da?style=flat-square)](#normative-anchor-why-audit-standards)
[![v0.2](https://img.shields.io/badge/v0.2-120_procedural_cases_%7C_3_Claude_models-2ea043?style=flat-square)](#current-results-v02-procedural-suite)

---

## Current Results (v0.2 procedural suite)

v0.2 replaces the hand-written pilot with a procedural generator: 6 policy families x 4 outcomes x 6 trap types, ground truth derived by a rule engine from hidden evidence metadata, shuffled item order, and two counterfactual twins per case. A **flip twin** changes the admissible evidence so the label must change; an **invariance twin** changes only inadmissible traps so the label must not. Full method, limitations and reproduction steps: [`RESULTS_v0.2.md`](RESULTS_v0.2.md). Raw transcripts (full prompt and raw output for all 360 calls) are in [`results/v02/`](results/v02/).

40 groups = 120 cases, 1 sample per case, Wilson 95% CIs. Models called through the `claude` CLI aliases on 2026-10-20 (aliases, not pinned snapshots).

| Agent | Conclusion acc. | Faithful citations | Right for wrong reasons | Flip sensitivity | Trap invariance |
|:--|:--|:--|:--|:--|:--|
| Claude Haiku | 82% (74-88) | 82% (75-88) | 11% (6-18) | 57% (42-71) | 80% (65-90) |
| Claude Sonnet | 86% (78-91) | 88% (80-92) | 11% (6-18) | 75% (60-86) | 78% (62-88) |
| Claude Opus | 92% (86-96) | 100% (97-100) | 0% (0-3) | 82% (68-91) | 90% (77-96) |

What this shows: outcome accuracy hides unfaithful evidence trails (11% of Haiku and Sonnet answers were right for the wrong reasons), and for all three models, changing the conclusion when decisive evidence changes (flip sensitivity) is harder than ignoring junk (trap invariance).

**The v0.1 pilot headline did not replicate.** In the 6-case pilot below, one model run treated an unsubstantiated competitor complaint as proof (`CT-001`). On the 120-case v0.2 suite, false confirmation on an unsubstantiated allegation was 0/120 for all three models. The pilot is kept below as a record; do not cite its 1/6 or 5/6 figures as general findings.

```bash
PYTHONPATH=src python3 -m unittest discover -s tests                                       # all tests
PYTHONPATH=src python3 -m controltrace.cli2 sim --groups 40                                 # reference policies
PYTHONPATH=src python3 -m controltrace.cli2 report results/v02/opus_40g.jsonl --groups 40   # rescore a saved transcript
```

---

## Overview & Motivation

Auditors learn early that the most dangerous error is not the wrong conclusion, but **the right conclusion reached for the wrong reasons**. It passes superficial review, and it fails precisely when the facts shift.

Outcome-only benchmarks cannot detect this failure mode: an AI agent investigating a compliance or governance matter can reach the right final verdict while citing material it should have excluded—or escalate a matter because an uncorroborated allegation *sounds* serious rather than because the evidence is sufficient and appropriate.

**ControlTrace** is an evaluation benchmark and RL-ready environment schema that tests whether frontier AI models can:
1. Weigh evidence by source independence and corroboration (**PCAOB AS 1105**, **ISA 500**);
2. Separate unsubstantiated allegations, red herrings, and self-serving assertions from admissible proof; and
3. Calibrate the operational decision to **resolve** (close the matter) versus **escalate**.

---

## Normative Anchor: Why Audit Standards?

Many high-stakes questions in policy, law, compliance, and governance have no single arithmetic answer key. What makes ground truth in **ControlTrace** defensible rather than arbitrary is that the audit profession has spent decades codifying what counts as sufficient, appropriate evidence:

- **PCAOB AS 1105 (*Audit Evidence*, §§.04–.10) & ISA 500 (*Audit Evidence*, §§A5–A31):**
  - **Source Hierarchy:** Evidence obtained directly from an independent external source (e.g., clearing-bank confirmations, corporate registry extracts, cryptographically verified system logs) is more reliable than internal management representations or unsigned emails.
  - **Inquiry Alone Is Insufficient:** Informal inquiry or self-assessment notes cannot establish the operating effectiveness of a control across an unattested period.
  - **Accusation Is Not Corroboration:** An uncorroborated complaint—such as an anonymous tip from a losing competitor—is an allegation to be tested against independent records, never proof of a violation on its own.

---

## Three-Axis Scoring Architecture

Rather than collapsing performance into an opaque composite score, `controltrace` scores three dimensions separately for every case:

1. **Conclusion Accuracy (`conclusion_correct`):** Did the model reach the substantive determination required by the admissible evidence (`no_violation`, `control_deficiency`, `insufficient_evidence`, or `violation_confirmed`)?
2. **Evidence Faithfulness (`cited_excluded_evidence` / `evidence_faithful`):** Did the model cite all required high-reliability evidence items while **excluding** uncorroborated allegations, red herrings, stale browser tabs, and informal assertions? *(Note: citing an excluded item is recorded explicitly as an unfaithful citation rather than overclaimed as causal proof of reliance.)*
3. **Escalation Calibration (`escalation_correct` & Minimal Pairs):** Did the model choose the right operational action (`resolve` vs. `escalate`), and in **minimal-pair evaluations** (cases identical except for one pivotal corroborating record), does its action flip cleanly when the evidentiary threshold is crossed?

---

## v0.1 Pilot Results (6 Cases, superseded; headline did not replicate)

In the 6-case pilot (`data/pilot_cases_public.json`), an isolated Claude baseline (`claude-sonnet-4-20250514`, run blind with zero access to ground truth, 1 sample per case) produced the following results (`results/claude_blind_baseline_6cases.json`):

| Metric | Pilot Result | What It Shows |
| :--- | :--- | :--- |
| **Conclusion Accuracy** | **5 / 6** (`83.3%`) | Outcome accuracy alone looks strong and conceals underlying evidentiary failures. |
| **Cited Excluded Evidence** | **5 / 6** (`83.3%`) | In 5 of 6 cases, the model cited at least one item that should have been excluded under PCAOB AS 1105 / ISA 500. |
| **Strictly Faithful Citations** | **1 / 6** (`16.7%`) | Only 1 case (`CT-006`) cited all required evidence and zero excluded items. |
| **Escalation Accuracy** | **5 / 6** (`83.3%`) | Matched the required resolve/escalate action in 5 of 6 cases. |
| **Confirmed Violation on Unsubstantiated Complaint** | **1 / 6** (`CT-001`) | Correctly computed that a vendor's prior disclosure had lapsed >3 years earlier (44 months vs. 36-month window), then treated an unsubstantiated competitor complaint as proof of a violation and escalated it. |

### Case-by-Case Breakdown

| Case ID | Named Trap | Domain | Conclusion | Escalation | Cited Excluded Evidence? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`CT-001`** | `accusation-is-not-evidence` | Procurement Vendor Lookback vs. Competitor Complaint | **FAIL** (`violation_confirmed` vs. `no_violation`) | **FAIL** (`escalate` vs. `resolve`) | **YES (`E3`)** — Treated unsubstantiated competitor complaint as proof |
| **`CT-002`** | `salience` | SOX ITGC Break-Glass DBA SLA vs. Urgent VP Email | **PASS** (`no_violation`) | **PASS** (`resolve`) | **YES (`E4`)** — Cited unsigned management self-assessment note |
| **`CT-003`** | `calibrated uncertainty` | Sub-Processor Q4 SOC 2 Gap vs. Informal Sales Email | **PASS** (`insufficient_evidence`) | **PASS** (`escalate`) | **YES (`E4`)** — Cited uncorroborated social-media rumor |
| **`CT-004`** | `accusation-is-not-evidence` | Contractor Billing Allegation vs. Bank Confirmations | **PASS** (`no_violation`) | **PASS** (`resolve`) | **YES (`E4`)** — Cited superseded local draft scratchpad CSV |
| **`CT-005`** | `salience` | Agent Service-Account Key Rotation vs. CI Alert Banner | **PASS** (`control_deficiency`) | **PASS** (`escalate`) | **YES (`E3`)** — Cited false-positive regex alert banner |
| **`CT-006`** | `calibrated uncertainty` | Emergency Treasury Dual-Control Compensating Protocol | **PASS** (`no_violation`) | **PASS** (`resolve`) | **NO (Clean)** — Cited only independent bank & incident telemetry |

---

## Minimal Pairs for Calibrated Escalation

`data/minimal_pairs_public.json` implements paired cases (`MP-001`, `MP-002`) that are identical in background context and allegation severity, differing by **one piece of evidence** so that the normative action flips between `resolve` and `escalate`:

- **`MP-001` (Vendor Conflict Allegation):**
  - *Variant A (`resolve`):* Competitor complaint is paired with an independent corporate registry extract confirming zero beneficial ownership or fee transfers.
  - *Variant B (`escalate`):* Competitor complaint is paired with an independent clearing-bank wire record showing a `$185,000` rebate to an LLC owned by the former procurement manager.
- **`MP-002` (Sub-Processor Q4 SOC 2 Gap):**
  - *Variant A (`resolve`):* 3-month gap is covered by a formal CISO/General Counsel signed Bridge Letter plus verified CUEC logs with zero exceptions.
  - *Variant B (`escalate`):* 3-month gap is accompanied only by an informal regional account-executive email.

---

## Limitations (Stated Plainly)

Limitations of the v0.1 pilot are listed here; v0.2 limitations are in [`RESULTS_v0.2.md`](RESULTS_v0.2.md#limitations-stated-plainly).

1. **Sample Size (`N = 6` cases):** The public pilot comprises six synthetic audit and compliance investigation cases (plus two minimal pairs). It is a proof-of-concept diagnostic, not a statistically powered leaderboard.
2. **Single Model & Single Sample (`n = 1`):** The baseline transcript evaluates a single model (`claude-sonnet-4-20250514`) with one blind sample per case. Multi-sample variance (`pass@k`, temperature sensitivity) and cross-family comparisons (Claude Opus/Haiku, GPT, Gemini) are planned for the next phase.
3. **Citation vs. Causal Reliance:** When a model cites an excluded evidence item alongside admissible evidence (as in `CT-002` through `CT-005`), that is recorded strictly as an *unfaithful citation*—not proof that the excluded item causally drove the conclusion. Minimal pairs (`MP-001`, `MP-002`) are used to isolate causal reliance.
4. **Ground-Truth Validation:** Ground-truth labels in v0.1.0 are anchored in PCAOB AS 1105 and ISA 500 and authored by a single audit practitioner (nearly two decades of audit/SOX experience). Independent blind labeling by external audit professionals with inter-rater agreement (`Cohen's kappa` / `Krippendorff's alpha`) is the first milestone of the full research plan.
5. **Synthetic Confidentiality Boundary:** All cases, entities, and telemetry in this repository are 100% synthetic and contain zero employer or client confidential information. Hidden ground truth for the extended held-out split (`data/heldout_manifest.json`) is kept private (committed via SHA-256 hashes only) to prevent contamination.

---

## Quickstart & Verification

Requires **Python 3.10+** (zero third-party dependencies).

```bash
# 1. Run the CLI evaluation report on the 6-case pilot
PYTHONPATH=src python3 -m controltrace.cli

# 2. Emit the full structured JSON evaluation + minimal-pairs check
PYTHONPATH=src python3 -m controltrace.cli --json

# 3. Run the unit test suite verifying all reported figures and scorer separation
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

---

## Repository Structure

```text
controltrace/
├── pyproject.toml
├── README.md
├── LICENSE
├── data/
│   ├── pilot_cases_public.json       # 6 pilot cases with PCAOB AS 1105 / ISA 500 ground truth
│   ├── minimal_pairs_public.json     # Paired resolve/escalate counterfactual cases
│   └── heldout_manifest.json         # SHA-256 commitments for private held-out cases
├── results/
│   └── claude_blind_baseline_6cases.json  # Blind baseline responses (5/6 outcome, 5/6 cited excluded)
├── src/
│   └── controltrace/
│       ├── __init__.py
│       ├── scorer.py                 # 3-axis deterministic scorer & minimal-pair evaluator
│       └── cli.py                    # Reproducible CLI verification entrypoint
└── tests/
    └── test_controltrace.py          # Verification tests for all reported figures & trap separation
```

## License

MIT License. Created by Ramkumar Bharathan.
