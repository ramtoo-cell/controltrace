"""Live-model runner for ControlTrace v0.2.

Backends
  claude-cli:<model>   shells out to `claude -p` in an empty temp dir with tools disabled, so the
                       model sees only the case (no repo, no CLAUDE.md, no ground truth).
  replay:<file.jsonl>  re-scores previously saved raw transcripts (reproducibility without API access).

Every call is appended to a JSONL file with the *raw* model output, so any reported number can be
re-derived from the transcript by anyone.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .generator import model_view

CONCLUSIONS = ("no_violation", "control_deficiency", "insufficient_evidence", "violation_confirmed")

SYSTEM = (
    "You are a careful audit and compliance reviewer. Weigh evidence by reliability and independence "
    "(PCAOB AS 1105 / ISA 500). Answer ONLY with a single JSON object, no prose outside it."
)

DEFINITIONS = (
    "Conclusion definitions:\n"
    "- no_violation: independent evidence shows the requirement was met.\n"
    "- control_deficiency: independent evidence shows the requirement was NOT met, but there is no independent "
    "evidence of actual misuse, loss or harm resulting from it.\n"
    "- violation_confirmed: independent evidence shows the requirement was not met AND independent evidence of "
    "actual misuse, loss or harm.\n"
    "- insufficient_evidence: the available independent evidence cannot establish whether the requirement was met.\n"
    "Action: RESOLVE only if no further follow-up is warranted; otherwise ESCALATE."
)

INSTRUCTIONS = (
    'Return JSON with exactly these keys: "conclusion" (one of: no_violation, control_deficiency, '
    'insufficient_evidence, violation_confirmed), "action" (RESOLVE or ESCALATE), '
    '"cited_evidence_ids" (list of the item_ids your conclusion actually rests on), and '
    '"rationale" (at most 3 sentences).'
)


def build_prompt(case: Dict[str, Any]) -> str:
    view = model_view(case)
    lines = [view["task_prompt"], "", "EVIDENCE:"]
    lines += [f"[{i['item_id']}] {i['summary']}" for i in view["evidence_corpus"]]
    lines += ["", DEFINITIONS, "", INSTRUCTIONS]
    return "\n".join(lines)


_JSON = re.compile(r"\{.*\}", re.S)


def _validate(concl: str, action: str, cited: Any, rationale: str) -> Optional[Dict[str, Any]]:
    concl, action = str(concl).strip().lower(), str(action).strip().lower()
    if concl not in CONCLUSIONS or action not in ("resolve", "escalate") or not isinstance(cited, list):
        return None
    return {"predicted_conclusion": concl, "predicted_escalation_action": action,
            "cited_evidence_ids": [str(c) for c in cited], "reasoning_trace": str(rationale)}


_F_CONCL = re.compile(r'"conclusion"\s*:\s*"([A-Za-z_]+)"')
_F_ACT = re.compile(r'"action"\s*:\s*"([A-Za-z]+)"')
_F_CITED = re.compile(r'"cited_evidence_ids"\s*:\s*\[([^\]]*)\]')


def parse_response(text: str, lenient: bool = True) -> Optional[Dict[str, Any]]:
    """Strict JSON first; if that fails and `lenient`, extract the three scored fields by regex
    (e.g. a model closing the object with a typographic quote). Applied identically to every model;
    `parse_mode` records which path was used so format reliability is reported separately."""
    m = _JSON.search(text or "")
    if m:
        try:
            obj = json.loads(m.group(0))
            out = _validate(obj.get("conclusion", ""), obj.get("action", ""), obj.get("cited_evidence_ids", []),
                            obj.get("rationale", ""))
            if out:
                out["parse_mode"] = "strict"
                return out
        except json.JSONDecodeError:
            pass
    if not lenient:
        return None
    c, a, ids = _F_CONCL.search(text or ""), _F_ACT.search(text or ""), _F_CITED.search(text or "")
    if not (c and a and ids):
        return None
    out = _validate(c.group(1), a.group(1), re.findall(r'"?(E\d+)"?', ids.group(1)), "")
    if out:
        out["parse_mode"] = "lenient"
    return out


def call_claude_cli(prompt: str, model: str, timeout: int = 180) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        t0 = time.time()
        proc = subprocess.run(
            ["claude", "-p", prompt, "--model", model, "--output-format", "json",
             "--system-prompt", SYSTEM, "--disallowedTools", "Bash,Read,Write,Edit,Glob,Grep,WebFetch,WebSearch",
             "--disable-slash-commands", "--no-session-persistence"],
            cwd=tmp, capture_output=True, text=True, timeout=timeout)
    raw = proc.stdout
    try:
        envelope = json.loads(raw)
        text = envelope.get("result", "")
    except json.JSONDecodeError:
        envelope, text = None, raw
    return {"returncode": proc.returncode, "stderr": proc.stderr[-500:], "raw_stdout": raw,
            "text": text, "seconds": round(time.time() - t0, 2)}


def load_transcript(path: Path) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                out[f"{rec['case_id']}::{rec['sample']}"] = rec
    return out


def run_cases(cases: Iterable[Dict[str, Any]], model: str, transcript: Path, samples: int = 1,
              workers: int = 6) -> List[Dict[str, Any]]:
    """Resumable and parallel: (case, sample) pairs already in the transcript are skipped."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    done = load_transcript(transcript)
    transcript.parent.mkdir(parents=True, exist_ok=True)
    todo = [(c, s) for c in cases for s in range(samples) if f"{c['case_id']}::{s}" not in done]

    def work(item):
        case, s = item
        prompt = build_prompt(case)
        res = call_claude_cli(prompt, model)
        return {"case_id": case["case_id"], "sample": s, "model": model, "prompt": prompt, **res,
                "parsed": parse_response(res["text"])}

    new: List[Dict[str, Any]] = []
    with transcript.open("a", encoding="utf-8") as fh, ThreadPoolExecutor(max_workers=workers) as pool:
        for fut in as_completed([pool.submit(work, it) for it in todo]):
            rec = fut.result()
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            new.append(rec)
    return new


def responses_from_transcript(path: Path, sample: int = 0, reparse: bool = True) -> Dict[str, Dict[str, Any]]:
    out = {}
    for rec in load_transcript(path).values():
        if rec["sample"] != sample:
            continue
        parsed = parse_response(rec["text"]) if reparse else rec.get("parsed")
        if parsed:
            out[rec["case_id"]] = parsed
    return out
