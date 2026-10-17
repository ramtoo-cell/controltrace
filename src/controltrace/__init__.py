"""ControlTrace: Evaluating AI Judgment Under Uncertainty (PCAOB AS 1105 / ISA 500)."""

from .scorer import (
    CaseScore,
    SuiteReport,
    load_pilot_cases,
    load_baseline_responses,
    score_response,
    evaluate_suite,
    evaluate_minimal_pairs,
)
from .env import ControlTraceEnv, InvestigationState

__all__ = [
    "CaseScore",
    "SuiteReport",
    "ControlTraceEnv",
    "InvestigationState",
    "load_pilot_cases",
    "load_baseline_responses",
    "score_response",
    "evaluate_suite",
    "evaluate_minimal_pairs",
]
__version__ = "0.1.0"
