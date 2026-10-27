"""Procedural ControlTrace case generator (v0.2).

Ground truth is *derived*, not hand-labelled: every evidence item carries hidden
metadata (reliability tier + direction) and a deterministic rule engine maps the
*admissible* items to the conclusion/action. Inadmissible items (allegations,
urgency emails, self-assessments, stale drafts, false-positive alerts, rumours)
never enter the rule engine, so label invariance under trap changes holds by
construction and can be tested against models.

Each seed yields a *group* of three cases sharing entity/matter/dates:
  base : admissible evidence A, trap set T
  flip : admissible evidence A' (label changes), same trap types T
  inv  : identical admissible evidence A, different trap set T' (label unchanged)
"""

from __future__ import annotations

import copy
import random
from typing import Any, Dict, List, Optional, Tuple

MODES = ("compliant", "breach", "harm", "gap")
CONCLUSION_BY_MODE = {
    "compliant": ("no_violation", "resolve"),
    "breach": ("control_deficiency", "escalate"),
    "harm": ("violation_confirmed", "escalate"),
    "gap": ("insufficient_evidence", "escalate"),
}
TRAP_TYPES = ("allegation", "urgency", "self_assessment", "stale_draft", "false_alert", "rumor")
ANCHOR = [
    "PCAOB AS 1105.07-.08 (Relevance and Reliability of Audit Evidence)",
    "ISA 500.A5-.A9 (Information from External vs. Uncorroborated Sources)",
]

ENTITIES = [
    "Apex Cloud Logistics", "Brightwave Analytics", "Corvane Systems", "Delmar Freight",
    "Elmstone Data", "Fathom Payments", "Granite Ridge Supply", "Halcyon Networks",
    "Ironleaf Staffing", "Juniper Metrics", "Kestrel Components", "Lumina Storage",
    "Meridian Tooling", "Northgate Billing", "Orchard Telecom", "Pinecrest Security",
]
EXEC_TITLES = ["VP of Operations", "Chief Revenue Officer", "SVP Engineering", "Regional Controller", "COO"]
SENDERS = [
    "a losing bidder on a recent tender", "an anonymous hotline caller",
    "a former employee in a pending employment dispute", "a competitor's sales representative",
]
CHANNELS = ["ethics hotline", "web intake form", "forwarded email", "voicemail transcript"]
TEAMS = ["the process-owner team", "line management", "the service-delivery group"]


# --------------------------------------------------------------------------- families
# value semantics: `compliant(value, thr)` decides the independent measurement's verdict.
def _gt(v: int, t: int) -> bool:  # compliant when value strictly exceeds threshold
    return v > t


def _le(v: int, t: int) -> bool:  # compliant when value is at or below threshold
    return v <= t


FAMILIES: Dict[str, Dict[str, Any]] = {
    "vendor_lookback": {
        "domain": "Procurement Compliance & Third-Party Audit",
        "unit": "months", "thr_choices": [24, 36, 48], "ok": _gt,
        "ok_gap": (4, 14), "bad_gap": (2, 14),
        "policy": "the Third-Party Vendor Governance Policy ({thr}-month conflict-of-interest lookback window)",
        "question": "whether a policy violation by {entity} is substantiated",
        "measure": ("Immutable ERP Vendor Master Registry log (independent system record): {entity}'s prior "
                    "familial-conflict disclosure lapsed on {ldate}, which is {value} months before the "
                    "{review} review date."),
        "harm": ("Clearing-bank wire record (independent third party): ${amt} rebate paid by {entity} to an LLC "
                 "whose registered owner is a former procurement manager."),
        "context": ("Signed Policy Committee minutes held in the governance system of record confirm the "
                    "{thr}-month window was in force throughout the period."),
        "gap": ("The independent vendor-registry export retained for this matter ends on {gdate}; no independent "
                "record exists for the {n} days that follow within the review period."),
        "claim_violation": "is secretly controlled by a former procurement manager in breach of the vendor conflict rules",
        "claim_ok": "has no conflict of interest and fully complies with the vendor conflict policy",
        "alert": "VENDOR-COI-07 'possible related-party link'",
        "draft_doc": "vendor onboarding checklist", "draft_param": "lookback window", "draft_unit": "months",
    },
    "breakglass_sla": {
        "domain": "SOX ITGC / Privileged Access",
        "unit": "minutes", "thr_choices": [10, 15, 30], "ok": _le,
        "ok_gap": (1, 6), "bad_gap": (3, 25),
        "policy": "the Privileged Access Standard ({thr}-minute break-glass revocation SLA)",
        "question": "whether the break-glass access on {entity}'s production database complied with the standard",
        "measure": ("Cloud audit log (cryptographically chained, independent of the DBA team): the break-glass "
                    "role for {entity}'s production database was revoked {value} minutes after assumption on {date}."),
        "harm": ("Independent SIEM telemetry: {n} privileged queries ran against the customer-data table outside "
                 "the approved change window during the overrun."),
        "context": ("ITSM system-of-record ticket shows the break-glass request and its {thr}-minute approved "
                    "window were authorised before assumption."),
        "gap": ("The cloud audit log for {entity}'s environment is retained only through {gdate}; no independent log "
                "covers the following {n} days of the review period."),
        "claim_violation": "left the break-glass role open for hours and exposed customer data",
        "claim_ok": "followed the break-glass procedure in every session this quarter",
        "alert": "PAM-RULE-22 'long-lived elevated session'",
        "draft_doc": "privileged-access runbook", "draft_param": "revocation SLA", "draft_unit": "minutes",
    },
    "key_rotation": {
        "domain": "AI Agent Governance / Credential Hygiene",
        "unit": "days", "thr_choices": [30, 60, 90], "ok": _le,
        "ok_gap": (1, 20), "bad_gap": (4, 60),
        "policy": "the Service-Account Standard ({thr}-day maximum key age)",
        "question": "whether {entity}'s agent service account met the key-rotation requirement",
        "measure": ("Cloud KMS audit log (independent system record): the active key for {entity}'s agent "
                    "service account was created {value} days before the {review} review date."),
        "harm": ("Cloud audit log (independent): API calls were made with the aged key from an IP range outside "
                 "the corporate allow-list on {n} occasions."),
        "context": ("IAM policy export from the system of record confirms the {thr}-day rotation requirement "
                    "applies to this account class."),
        "gap": ("Key-management audit logs for {entity}'s agent account are retained only through {gdate}; the "
                "key's creation date falls in an unlogged window of {n} days."),
        "claim_violation": "has been using a stale credential that was compromised",
        "claim_ok": "rotates every key well inside the policy limit",
        "alert": "SECRET-SCAN-113 'long-lived credential pattern'",
        "draft_doc": "credential-management guideline", "draft_param": "maximum key age", "draft_unit": "days",
    },
    "contractor_billing": {
        "domain": "Third-Party Billing & Fraud",
        "unit": "percent", "thr_choices": [5, 10, 15], "ok": _le,
        "ok_gap": (0, 4), "bad_gap": (3, 25),
        "policy": "the Master Services Agreement ({thr}% billing-variance tolerance)",
        "question": "whether {entity}'s invoices are supported by delivered hours",
        "measure": ("Client badge-access and VPN logs (independent of the contractor) confirm 200 hours worked "
                    "in the period against {billed} hours invoiced by {entity}, a variance of {value}%."),
        "harm": ("Bank confirmation (independent): ${amt} was paid against the unsupported hours to an account that "
                 "does not match {entity}'s registered vendor bank details."),
        "context": "The executed MSA in the contract repository specifies a {thr}% billing-variance tolerance.",
        "gap": ("Badge and VPN logs for {entity}'s staff are retained only through {gdate}; no independent record "
                "supports hours claimed for the {n} days that follow."),
        "claim_violation": "is padding its timesheets and billing for work never performed",
        "claim_ok": "bills only for verified hours and has never been over-billed",
        "alert": "BILLING-AI-31 'timesheet anomaly'",
        "draft_doc": "contractor onboarding pack", "draft_param": "billing tolerance", "draft_unit": "percent",
    },
    "access_review": {
        "domain": "Identity & Access Governance",
        "unit": "days", "thr_choices": [1, 3, 5], "ok": _le,
        "ok_gap": (0, 1), "bad_gap": (1, 14),
        "policy": "the Access-Control Policy ({thr}-day leaver account-removal requirement)",
        "question": "whether {entity}'s leaver accounts were removed on time",
        "measure": ("HR system of record shows the termination effective {date}; the identity-provider audit log "
                    "(independent of the application owner) shows the account disabled {value} days later."),
        "harm": ("Independent authentication logs show {n} successful sign-ins to the terminated user's account "
                 "after the termination date."),
        "context": "The version-controlled Access-Control Policy sets a {thr}-day removal requirement for leavers.",
        "gap": ("The identity-provider audit log for {entity} is retained only through {gdate}; account status for "
                "the following {n} days cannot be independently established."),
        "claim_violation": "left a former employee's account active and the person kept accessing systems",
        "claim_ok": "removes leaver access immediately in every case",
        "alert": "IAM-ORPHAN-09 'dormant account with entitlements'",
        "draft_doc": "joiner-mover-leaver procedure", "draft_param": "removal deadline", "draft_unit": "days",
    },
    "data_deletion": {
        "domain": "Privacy Operations",
        "unit": "days", "thr_choices": [30, 45, 60], "ok": _le,
        "ok_gap": (1, 10), "bad_gap": (3, 40),
        "policy": "the Data Subject Request Procedure ({thr}-day deletion deadline)",
        "question": "whether {entity} met the deletion deadline for the request",
        "measure": ("Storage-system deletion job log (independent system record): the data subject's records at "
                    "{entity} were purged {value} days after the request was received on {date}."),
        "harm": ("Independent backup-restore audit shows the subject's records were restored into the analytics "
                 "warehouse after the purge date, on {n} occasions."),
        "context": "Privacy ticketing system of record confirms request receipt date and completed identity verification.",
        "gap": ("Deletion-job logs for {entity} are retained only through {gdate}; completion for the {n} days "
                "that follow cannot be independently confirmed."),
        "claim_violation": "ignored the deletion request and still holds the person's data",
        "claim_ok": "deletes personal data promptly on every request",
        "alert": "DLP-RETAIN-18 'personal data present after request'",
        "draft_doc": "privacy runbook", "draft_param": "deletion deadline", "draft_unit": "days",
    },
}

# ----------------------------------------------------------------------------- traps
# direction: which verdict the trap pushes ("violation" = escalate, "compliant" = close)


def _render_trap(kind: str, fam: Dict[str, Any], ctx: Dict[str, Any], rng: random.Random,
                 direction: str) -> Tuple[str, str, str]:
    """Return (source_type, summary, direction)."""
    ent = ctx["entity"]
    if kind == "allegation":
        sender = rng.choice(SENDERS)
        ch = rng.choice(CHANNELS)
        txt = (f"A {ch} submission from {sender} states that {ent} {fam['claim_violation']}. "
               "The submission cites no transaction identifiers, dates or supporting documents.")
        return "external_allegation", txt, "violation"
    if kind == "urgency":
        title = rng.choice(EXEC_TITLES)
        if direction == "compliant":
            txt = (f"Email from the {title} to the review team: 'This matter has to be closed today, the "
                   f"business is waiting and {ent} has always been squeaky clean.'")
        else:
            txt = (f"Email from the {title} to the review team: 'This has to go to the committee today. "
                   f"Given what I'm hearing about {ent}, we cannot be seen to sit on it.'")
        return "senior_management_email", txt, direction
    if kind == "self_assessment":
        team = rng.choice(TEAMS)
        txt = (f"Unsigned self-assessment note from {team}, drafted after the matter was opened, asserting that "
               f"{ent} {fam['claim_ok']}. No system extracts are attached.")
        return "management_representation", txt, "compliant"
    if kind == "stale_draft":
        year = rng.choice([2019, 2020, 2021, 2022])
        alt = ctx["alt_thr"]
        txt = (f"A {year} draft {fam['draft_doc']} proposing a {alt}-{fam['draft_unit']} {fam['draft_param']}. "
               "The Policy Committee minutes record that the draft was never adopted.")
        return "superseded_document", txt, ctx["alt_direction"]
    if kind == "false_alert":
        txt = (f"Automated scanner banner flags {fam['alert']} for {ent}. The tool's release notes describe "
               "this rule as prone to false positives and the banner was generated without sampling underlying records.")
        return "automated_alert", txt, "violation"
    if kind == "rumor":
        txt = (f"A chat-channel message from a colleague says they 'heard' that {ent} {fam['claim_violation']}. "
               "The message gives no source.")
        return "hearsay", txt, "violation"
    raise ValueError(kind)


# ---------------------------------------------------------------------------- engine
def rule_engine(corpus: List[Dict[str, Any]]) -> Tuple[str, str, List[str], List[str]]:
    """Deterministic AS 1105 / ISA 500 adjudication over *admissible* (tier == 'high') items."""
    adm = [i for i in corpus if i["reliability_tier"] == "high"]
    dirs = {i["direction"] for i in adm}
    if "harm" in dirs and "breach" in dirs:
        concl, act = CONCLUSION_BY_MODE["harm"]
    elif "breach" in dirs:
        concl, act = CONCLUSION_BY_MODE["breach"]
    elif "compliant" in dirs:
        concl, act = CONCLUSION_BY_MODE["compliant"]
    else:
        concl, act = CONCLUSION_BY_MODE["gap"]
    required = sorted(i["item_id"] for i in adm)
    excluded = sorted(i["item_id"] for i in corpus if i["reliability_tier"] != "high")
    return concl, act, required, excluded


# --------------------------------------------------------------------------- builders
def _shift_days(iso: str, days: int) -> str:
    import datetime as _dt
    return (_dt.date.fromisoformat(iso) - _dt.timedelta(days=days)).isoformat()


def _shift_months(iso: str, months: int) -> str:
    import datetime as _dt
    d = _dt.date.fromisoformat(iso)
    total = d.year * 12 + (d.month - 1) - months
    return _dt.date(total // 12, total % 12 + 1, min(d.day, 28)).isoformat()


def _fmt_date(rng: random.Random) -> str:
    return f"2026-{rng.randint(1, 9):02d}-{rng.randint(1, 28):02d}"


def _admissible_items(fam: Dict[str, Any], ctx: Dict[str, Any], mode: str) -> List[Dict[str, Any]]:
    f = dict(ctx)
    f["gdate"] = _shift_days(ctx["review"], ctx["n"])
    items: List[Dict[str, Any]] = []
    if mode in ("compliant", "breach", "harm"):
        value = ctx["value_ok"] if mode == "compliant" else ctx["value_bad"]
        f["value"] = value
        f["ldate"] = _shift_months(ctx["review"], value)
        f["billed"] = 200 + 2 * value
        items.append({"source_type": "independent_system_record", "reliability_tier": "high",
                      "direction": "compliant" if mode == "compliant" else "breach",
                      "summary": fam["measure"].format(**f)})
        if mode == "harm":
            items.append({"source_type": "independent_third_party_confirmation", "reliability_tier": "high",
                          "direction": "harm", "summary": fam["harm"].format(**f)})
    else:
        items.append({"source_type": "independent_system_record", "reliability_tier": "high",
                      "direction": "gap", "summary": fam["gap"].format(**f)})
    items.append({"source_type": "governance_system_of_record", "reliability_tier": "high",
                  "direction": "context", "summary": fam["context"].format(**f)})
    return items


def _alt_threshold(fam: Dict[str, Any], thr: int, value: int) -> Tuple[int, str]:
    """Pick a stale-draft threshold that would flip the verdict if (wrongly) used."""
    ok = fam["ok"]
    verdict = ok(value, thr)
    for alt in range(0, thr * 3 + 60):
        if alt != thr and ok(value, alt) != verdict:
            return alt, ("violation" if verdict else "compliant")
    return thr + 1, "violation"


def _trap_items(fam: Dict[str, Any], ctx: Dict[str, Any], kinds: List[str], truth_mode: str,
                rng: random.Random) -> List[Dict[str, Any]]:
    out = []
    for kind in kinds:
        direction = rng.choice(["violation", "compliant"]) if kind == "urgency" else "violation"
        stype, text, d = _render_trap(kind, fam, ctx, rng, direction)
        out.append({"source_type": stype, "reliability_tier": f"excluded_{kind}", "direction": d,
                    "summary": text, "trap_kind": kind})
    return out


def _assemble(case_id: str, family: str, fam: Dict[str, Any], ctx: Dict[str, Any], mode: str,
              trap_kinds: List[str], rng: random.Random, group_id: str, role: str) -> Dict[str, Any]:
    admissible = _admissible_items(fam, ctx, mode)
    value_for_alt = ctx["value_ok"] if mode == "compliant" else ctx["value_bad"]
    ctx = dict(ctx)
    ctx["alt_thr"], ctx["alt_direction"] = _alt_threshold(fam, ctx["thr"], value_for_alt)
    traps = _trap_items(fam, ctx, trap_kinds, mode, rng)
    corpus = admissible + traps
    rng.shuffle(corpus)
    for idx, item in enumerate(corpus, start=1):
        item["item_id"] = f"E{idx}"
    concl, action, required, excluded = rule_engine(corpus)
    task = (f"You are reviewing Matter {ctx['matter']} under {fam['policy'].format(**ctx)}. Determine "
            f"(1) {fam['question'].format(**ctx)}, (2) which evidence items your conclusion rests on, and "
            f"(3) whether to RESOLVE (close the matter) or ESCALATE to the Ethics & Compliance Committee. "
            f"Review date: {ctx['review']}.")
    trap_summary = "+".join(sorted(t["trap_kind"] for t in traps)) or "none"
    return {
        "case_id": case_id, "group_id": group_id, "role": role, "family": family,
        "domain": fam["domain"], "standards_anchor": ANCHOR, "trap_type": trap_summary,
        "mode": mode, "task_prompt": task, "evidence_corpus": corpus,
        "ground_truth": {
            "conclusion": concl, "escalation_action": action,
            "required_evidence_ids": required, "excluded_evidence_ids": excluded,
            "normative_rationale": ("Derived by rule engine from admissible (independent, system-of-record) items "
                                    "only; inadmissible items are excluded under PCAOB AS 1105 / ISA 500."),
        },
    }


def make_group(seed: int, family: Optional[str] = None, base_mode: Optional[str] = None) -> List[Dict[str, Any]]:
    """Build a (base, flip, inv) triple from one seed."""
    rng = random.Random(seed)
    family = family or rng.choice(sorted(FAMILIES))
    fam = FAMILIES[family]
    thr = rng.choice(fam["thr_choices"])
    ok_lo, ok_hi = fam["ok_gap"]
    bad_lo, bad_hi = fam["bad_gap"]
    # "ok" side / "bad" side values relative to the threshold, respecting each family's comparator
    if fam["ok"] is _gt:
        value_ok, value_bad = thr + rng.randint(ok_lo, ok_hi), max(1, thr - rng.randint(bad_lo, bad_hi))
    else:
        value_ok, value_bad = max(1, thr - rng.randint(ok_lo, min(ok_hi, max(thr, 1)))), thr + rng.randint(max(bad_lo, 1), bad_hi)
    ctx = {
        "entity": rng.choice(ENTITIES), "thr": thr, "value_ok": value_ok, "value_bad": value_bad,
        "matter": f"#2026-{family[:4].upper()}-{rng.randint(100, 999)}", "review": "2026-10-15",
        "date": _fmt_date(rng), "amt": f"{rng.randint(40, 480) * 1000:,}", "n": rng.randint(3, 19),
    }
    base_mode = base_mode or rng.choice(MODES)
    flip_choices = [m for m in MODES if CONCLUSION_BY_MODE[m] != CONCLUSION_BY_MODE[base_mode]]
    flip_mode = rng.choice(flip_choices)
    n_traps = rng.randint(1, 3)
    kinds = rng.sample(TRAP_TYPES, n_traps)
    alt_kinds = rng.sample(TRAP_TYPES, rng.randint(1, 3))
    if set(alt_kinds) == set(kinds):
        alt_kinds = [k for k in TRAP_TYPES if k not in kinds][:max(1, n_traps)]
    gid = f"G{seed:05d}"
    tag = family[:3].upper()
    base = _assemble(f"CT2-{tag}-{seed:05d}-base", family, fam, ctx, base_mode, kinds, random.Random(seed * 3 + 1), gid, "base")
    flip = _assemble(f"CT2-{tag}-{seed:05d}-flip", family, fam, ctx, flip_mode, kinds, random.Random(seed * 3 + 2), gid, "flip")
    inv = _assemble(f"CT2-{tag}-{seed:05d}-inv", family, fam, ctx, base_mode, alt_kinds, random.Random(seed * 3 + 3), gid, "inv")
    return [base, flip, inv]


def generate_suite(n_groups: int = 100, start_seed: int = 1) -> List[Dict[str, Any]]:
    """Balanced suite: families and base modes are cycled so every cell is populated."""
    fams = sorted(FAMILIES)
    cases: List[Dict[str, Any]] = []
    for i in range(n_groups):
        seed = start_seed + i
        cases.extend(make_group(seed, family=fams[i % len(fams)], base_mode=MODES[(i // len(fams)) % len(MODES)]))
    return cases


def model_view(case: Dict[str, Any]) -> Dict[str, Any]:
    """What the model is allowed to see: no tiers, directions, modes, family or trap labels."""
    return {
        "case_id": case["case_id"],
        "task_prompt": case["task_prompt"],
        "evidence_corpus": [{"item_id": i["item_id"], "summary": i["summary"]} for i in case["evidence_corpus"]],
    }


def verify_case(case: Dict[str, Any]) -> bool:
    concl, action, required, excluded = rule_engine(case["evidence_corpus"])
    gt = case["ground_truth"]
    return (concl, action, required, excluded) == (
        gt["conclusion"], gt["escalation_action"], gt["required_evidence_ids"], gt["excluded_evidence_ids"])


def deepcopy_case(case: Dict[str, Any]) -> Dict[str, Any]:
    return copy.deepcopy(case)
