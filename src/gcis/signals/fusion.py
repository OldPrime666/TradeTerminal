from dataclasses import dataclass
from typing import List

@dataclass
class FusionResult:
    direction: str | None
    setup_score: int
    mandatory_gates: List[str]
    confluence_count: int
    confluence_quality: float
    conflicting_evidence: List[str]
    supporting_evidence: List[str]
    eligibility: bool
    probability_status: str

def fuse(strategy_results: list, config: dict) -> FusionResult:
    """
    Hard gates multiplicative — any failure blocks.
    Surviving evidence combined into setup_score 0-100 from versioned weights.
    For P0 we have single strategy ICT-A, so fusion trivial.
    """
    if not strategy_results:
        return FusionResult(None, 0, ["NO_STRATEGY"], 0, 0.0, [], [], False, "INSUFFICIENT_DATA")
    # take best eligible
    eligible = [r for r in strategy_results if r.eligible]
    if not eligible:
        # take highest score among ineligible for display
        best = max(strategy_results, key=lambda x: x.setup_score)
        return FusionResult(best.direction, best.setup_score, best.reason_codes, 0, 0.0, best.reason_codes, best.evidence, False, "INSUFFICIENT_DATA")
    best = max(eligible, key=lambda x: x.setup_score)
    # confluence simplified
    return FusionResult(best.direction, best.setup_score, [], 1, 0.8, [], best.evidence, True, "NOT_REQUIRED")
