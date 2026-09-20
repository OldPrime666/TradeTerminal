"""
SIG-02 Fusion setup_score 0-100 with versioned weights
Weights from config/default.yaml setup_score.weights:
  htf_alignment 20, liquidity_sweep_quality 20, displacement_quality 15,
  zone_quality 15, regime_compat 10, session_context 5, volume_confirmation 5, cost_efficiency 10
Sum 100. Grades A 85 B 70 C 55.
For single strategy ICT-A, fusion is straightforward but must compute weighted score
and conflicting/supporting evidence.
"""
from dataclasses import dataclass
from typing import List, Optional
from decimal import Decimal

@dataclass
class FusionResult:
    direction: Optional[str]
    setup_score: int
    grade: str
    mandatory_gates: List[str]
    confluence_count: int
    confluence_quality: float
    conflicting_evidence: List[str]
    supporting_evidence: List[str]
    eligibility: bool
    probability_status: str
    evidence_hash: str

def _grade_from_score(score: int, grades_cfg: dict) -> str:
    # grades_cfg {A:85, B:70, C:55}
    if score >= grades_cfg.get("A", 85):
        return "A"
    if score >= grades_cfg.get("B", 70):
        return "B"
    if score >= grades_cfg.get("C", 55):
        return "C"
    return "D"

def compute_setup_score(strategy_result, view, symbol: str, config: dict) -> int:
    """
    Weighted 0-100 based on evidence presence and strategy fields.
    This mirrors code thresholds and is deterministic.
    """
    weights = config.get("setup_score", {}).get("weights", {
        "htf_alignment": 20,
        "liquidity_sweep_quality": 20,
        "displacement_quality": 15,
        "zone_quality": 15,
        "regime_compat": 10,
        "session_context": 5,
        "volume_confirmation": 5,
        "cost_efficiency": 10,
    })
    evidence = getattr(strategy_result, "evidence", []) or []
    evidence_str = " ".join([str(e) for e in evidence]).lower()
    score = 0
    # htf_alignment: bonus if evidence contains HTF bias aligned
    if "htf bias bullish" in evidence_str or "htf bias bearish" in evidence_str or "htf" in evidence_str:
        # check that bias not incompatible
        if "htf_bias" not in evidence_str or "incompatible" not in evidence_str:
            score += weights.get("htf_alignment", 20)
    else:
        # if no HTF mention, assume 0
        pass
    # liquidity_sweep_quality: presence of confirmed sweep
    if "sweep" in evidence_str and ("confirmed" in evidence_str or "bullish-confirmed" in evidence_str):
        # check quality: if at least 1 sweep
        score += weights.get("liquidity_sweep_quality", 20)
    # displacement_quality
    if "displacement" in evidence_str:
        try:
            # parse displacements count? evidence like "displacements 3"
            import re
            m = re.search(r"displacements\s+(\d+)", evidence_str)
            if m and int(m.group(1)) > 0:
                score += weights.get("displacement_quality", 15)
            elif "displacement" in evidence_str:
                score += weights.get("displacement_quality", 15) // 2
        except:
            score += weights.get("displacement_quality", 15)
    # zone_quality: FVG or OB entry
    if "fvg" in evidence_str or "ob" in evidence_str or "entry fvg" in evidence_str or "entry ob" in evidence_str:
        score += weights.get("zone_quality", 15)
    # regime_compat: regime compatibility flag
    if getattr(strategy_result, "regime_compatibility", False):
        score += weights.get("regime_compat", 10)
    # session_context: simplified always 5 if eligible else 0 (session inactive would be gate failure)
    if strategy_result.eligible:
        score += weights.get("session_context", 5)
    # volume_confirmation: if evidence mentions volume or we assume true
    if "volume" in evidence_str:
        score += weights.get("volume_confirmation", 5)
    else:
        # for P06 we still give partial if eligible
        if strategy_result.eligible:
            score += weights.get("volume_confirmation", 5) // 2
    # cost_efficiency: if netR evidence present and > threshold
    if "netr" in evidence_str or "cost" in evidence_str:
        # check netR values
        if "netr" in evidence_str:
            score += weights.get("cost_efficiency", 10)
        else:
            score += weights.get("cost_efficiency", 10) // 2
    else:
        if strategy_result.eligible:
            score += weights.get("cost_efficiency", 5)
    # Clamp to strategy_result.setup_score if provided? Use max
    # The strategy already computed a heuristic score (0-100). We combine: take strategy score as baseline but ensure weighted sum matches.
    # For P06 we trust weighted sum, but also incorporate strategy's own score magnitude
    strat_score = getattr(strategy_result, "setup_score", 0) or 0
    # blend: weighted score is primary, but if strat_score higher, take it (bounded)
    final = max(score, min(100, strat_score))
    # However if strategy not eligible, cap at 45 (as per ict_a returns 45 for RR fail etc)
    if not strategy_result.eligible:
        final = min(final, strat_score if strat_score else 45)
    return int(min(100, max(0, final)))

def fuse(strategy_results: list, config: dict, view=None, symbol: str = None) -> FusionResult:
    """
    Hard gates multiplicative — any failure blocks.
    Surviving evidence combined into setup_score 0-100 from versioned weights.
    For P0 we have single strategy ICT-A, so fusion trivial but now weighted.
    Returns FusionResult with evidence_hash, grade, eligibility.
    """
    import hashlib, json
    grades_cfg = config.get("setup_score", {}).get("grades", {"A":85,"B":70,"C":55})
    if not strategy_results:
        return FusionResult(None, 0, "D", ["NO_STRATEGY"], 0, 0.0, [], [], False, "INSUFFICIENT_DATA", hashlib.sha256(b"no_strategy").hexdigest()[:16])
    # take best eligible by setup_score, else best ineligible for display
    eligible = [r for r in strategy_results if r.eligible]
    if not eligible:
        best = max(strategy_results, key=lambda x: x.setup_score)
        # compute weighted but still blocked
        score = compute_setup_score(best, view, symbol or "BTCUSDT", config)
        # evidence hash
        ev = getattr(best, "evidence", [])
        h = hashlib.sha256(json.dumps(ev, sort_keys=True).encode()).hexdigest()[:16]
        # conflicting vs supporting: reason_codes are conflicting
        return FusionResult(
            direction=best.direction,
            setup_score=score,
            grade=_grade_from_score(score, grades_cfg),
            mandatory_gates=list(getattr(best, "reason_codes", [])),
            confluence_count=0,
            confluence_quality=0.0,
            conflicting_evidence=list(getattr(best, "reason_codes", [])),
            supporting_evidence=list(getattr(best, "evidence", [])),
            eligibility=False,
            probability_status="INSUFFICIENT_DATA",
            evidence_hash=h,
        )
    # at least one eligible — pick highest weighted score
    # compute weighted scores for each
    scored = []
    for r in eligible:
        ws = compute_setup_score(r, view, symbol or "BTCUSDT", config)
        scored.append((ws, r))
    best_ws, best = max(scored, key=lambda x: x[0])
    # confluence: number of strategies supporting same direction
    same_dir = [r for r in eligible if r.direction == best.direction]
    confluence = len(same_dir)
    # evidence hash over best evidence
    import hashlib, json
    h = hashlib.sha256(json.dumps(getattr(best, "evidence", []), sort_keys=True).encode()).hexdigest()[:16]
    return FusionResult(
        direction=best.direction,
        setup_score=best_ws,
        grade=_grade_from_score(best_ws, grades_cfg),
        mandatory_gates=[],
        confluence_count=confluence,
        confluence_quality=0.8 if confluence>0 else 0.0,
        conflicting_evidence=[],
        supporting_evidence=list(getattr(best, "evidence", [])),
        eligibility=True,
        probability_status="NOT_REQUIRED",
        evidence_hash=h,
    )
