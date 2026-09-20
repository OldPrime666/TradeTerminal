"""
PRB Display Gate — controls when probability is shown vs N/A.
Config: display_gate min_train_events_effective 100, min_oos_events 50, max_ci_halfwidth 0.10, max_ece 0.05, require_version_match
PRB-01..12 Tier A
"""
from typing import Dict, Any, List
from gcis.probability.calibration import compute_ece

def check_display_gate(train_n: int, oos_n: int, ci_halfwidth: float, ece: float, version_match: bool, drift_flag: bool = False) -> Dict[str,Any]:
    """
    Return gate decision: pass if all thresholds meet, else fail with reasons.
    Deterministic.
    """
    reasons = []
    ok = True
    # thresholds from config default
    min_train = 100
    min_oos = 50
    max_ci = 0.10
    max_ece = 0.05
    if train_n < min_train:
        reasons.append(f"TRAIN_N {train_n}<{min_train}")
        ok=False
    if oos_n < min_oos:
        reasons.append(f"OOS_N {oos_n}<{min_oos}")
        ok=False
    if ci_halfwidth is not None and ci_halfwidth > max_ci:
        reasons.append(f"CI_HALFWIDTH {ci_halfwidth:.3f}>{max_ci}")
        ok=False
    if ece is not None and ece > max_ece:
        reasons.append(f"ECE {ece:.3f}>{max_ece}")
        ok=False
    if not version_match:
        reasons.append("VERSION_MISMATCH")
        ok=False
    if drift_flag:
        reasons.append("DRIFT_DETECTED")
        ok=False
    status = "PASS" if ok else "FAIL"
    # PRB-12: at L0-L2 display as N/A when gate fails, not 0%/50%
    display = {"p_display": None if not ok else "SHOW", "ev_display": None if not ok else "SHOW"}
    return {"pass": ok, "status": status, "reasons": reasons, "display": display, "gate_inputs": {"train_n":train_n,"oos_n":oos_n,"ci_halfwidth":ci_halfwidth,"ece":ece,"version_match":version_match,"drift_flag":drift_flag}}

def gate_from_stats(train_wins: int, train_total: int, oos_wins: int, oos_total: int, ci_halfwidth: float, y_true: List[int] | None, y_prob: List[float] | None, version_match: bool = True, drift_flag: bool = False) -> Dict[str,Any]:
    """
    Helper to compute ece from y arrays if provided, else need ece passed.
    """
    ece = None
    if y_true is not None and y_prob is not None:
        ece = compute_ece(y_true, y_prob)
    # also allow explicit ece via ci? but compute here
    return check_display_gate(train_total, oos_total, ci_halfwidth, ece, version_match, drift_flag)

def version_match_check(current_version: str, trained_version: str) -> bool:
    return current_version == trained_version
