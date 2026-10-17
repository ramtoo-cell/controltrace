"""RL Environment wrapper for ControlTrace (PCAOB AS 1105 / ISA 500).

Turns each ControlTrace audit investigation case (and minimal pair) into a multi-step
reinforcement learning environment with decomposed process and outcome rewards:
  - inspect(item_id): Read an evidence item from the corpus
  - mark_admissible(item_id): Cite an item as sufficient & appropriate under AS 1105 / ISA 500
  - mark_excluded(item_id): Exclude an item as uncorroborated allegation, hearsay, or red herring
  - submit(conclusion, escalation_action): Conclude and choose resolve vs. escalate
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple
from .scorer import score_response


@dataclass
class InvestigationState:
    case_id: str
    task_prompt: str
    available_item_ids: List[str]
    inspected_ids: Set[str] = field(default_factory=set)
    cited_admissible_ids: Set[str] = field(default_factory=set)
    flagged_excluded_ids: Set[str] = field(default_factory=set)
    done: bool = False
    step_count: int = 0


class ControlTraceEnv:
    """Gym-style step environment for training and evaluating evidentiary skepticism."""

    def __init__(self, case: Dict[str, Any], max_steps: int = 16) -> None:
        self.case = case
        self.max_steps = max_steps
        self._items_by_id = {
            item["item_id"]: item for item in case.get("evidence_corpus", [])
        }
        self.state = self.reset()

    def reset(self) -> InvestigationState:
        self.state = InvestigationState(
            case_id=self.case["case_id"],
            task_prompt=self.case["task_prompt"],
            available_item_ids=list(self._items_by_id.keys()),
        )
        return self.state

    def step(
        self, action: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], float, bool, Dict[str, Any]]:
        """Execute one environment step.

        Supported action types:
          - {"type": "inspect", "item_id": "E1"}
          - {"type": "cite", "item_id": "E1"}
          - {"type": "exclude", "item_id": "E3"}
          - {"type": "submit", "conclusion": "no_violation", "escalation_action": "resolve"}
        """
        if self.state.done:
            raise RuntimeError("Episode already terminated; call reset().")

        self.state.step_count += 1
        act_type = action.get("type")

        if act_type == "inspect":
            iid = str(action.get("item_id", ""))
            if iid not in self._items_by_id:
                return {"error": f"Unknown item_id: {iid}"}, -0.05, False, {}
            self.state.inspected_ids.add(iid)
            item = self._items_by_id[iid]
            return (
                {
                    "item_id": iid,
                    "summary": item["summary"],
                },
                0.0,
                False,
                {},
            )

        if act_type == "cite":
            iid = str(action.get("item_id", ""))
            if iid in self._items_by_id:
                self.state.cited_admissible_ids.add(iid)
                self.state.flagged_excluded_ids.discard(iid)
            return {"cited": sorted(self.state.cited_admissible_ids)}, 0.0, False, {}

        if act_type == "exclude":
            iid = str(action.get("item_id", ""))
            if iid in self._items_by_id:
                self.state.flagged_excluded_ids.add(iid)
                self.state.cited_admissible_ids.discard(iid)
            return {"excluded": sorted(self.state.flagged_excluded_ids)}, 0.0, False, {}

        if act_type == "submit":
            self.state.done = True
            response = {
                "case_id": self.case["case_id"],
                "predicted_conclusion": action.get("conclusion", ""),
                "predicted_escalation_action": action.get("escalation_action", ""),
                "cited_evidence_ids": sorted(self.state.cited_admissible_ids),
            }
            score = score_response(self.case, response)

            # Decomposed reward vector kept explicit so callers can inspect each component
            r_conclusion = 1.0 if score.conclusion_correct else -1.0
            r_escalation = 1.0 if score.escalation_correct else -1.0
            r_faithfulness = (
                1.0
                if score.evidence_faithful
                else (-1.0 if score.cited_excluded_evidence else -0.5)
            )
            # Heavy penalty for escalating on an unsubstantiated complaint (AS 1105 violation)
            r_skepticism_penalty = (
                -1.5 if score.confirmed_violation_on_unsubstantiated_complaint else 0.0
            )
            total_reward = round(
                (r_conclusion + r_escalation + r_faithfulness + r_skepticism_penalty)
                / 3.0,
                4,
            )

            info = {
                "case_score": score,
                "reward_components": {
                    "conclusion_reward": r_conclusion,
                    "escalation_reward": r_escalation,
                    "faithfulness_reward": r_faithfulness,
                    "unsubstantiated_complaint_penalty": r_skepticism_penalty,
                },
            }
            return {"terminal": True}, total_reward, True, info

        if self.state.step_count >= self.max_steps:
            self.state.done = True
            return {"error": "Max steps exceeded without submission"}, -1.0, True, {}

        return {"error": f"Unsupported action type: {act_type}"}, -0.05, False, {}
