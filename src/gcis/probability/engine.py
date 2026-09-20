"""
PRB Probability Engine — Tier A pooled EB + calibration + EV + gate.
Integrates census, walk-forward OOS, and signal outcomes.

Minimal P13: provides high-level function predict_with_gate(outcomes, candidate) where outcomes are list of dicts {strategy, direction, regime, win (0/1), return_r}
"""
from typing import List, Dict, Any, Tuple
from gcis.probability.empirical_bayes import select_pooling_tier, fit_beta_prior
from gcis.probability.calibration import calibration_report, detect_drift
from gcis.probability.ev_ranking import ev_from_trades
from gcis.probability.gates import check_display_gate

def _group_counts(outcomes: List[Dict[str,Any]], key_fn):
    wins = sum(1 for o in outcomes if o.get("win")==1 and key_fn(o))
    total = sum(1 for o in outcomes if key_fn(o))
    return wins, total

def probability_engine_predict(
    outcomes: List[Dict[str,Any]],
    candidate: Dict[str,Any],
    prior_strength: int = 20,
    oos_outcomes: List[Dict[str,Any]] | None = None,
    current_version: str = "0.2.0",
    trained_version: str = "0.2.0",
) -> Dict[str,Any]:
    """
    outcomes: full train outcomes (historical signal_outcomes)
    candidate: dict with keys strategy, direction, regime, liquidity_tier?, symbol?
    Returns dict with p_est, ci_halfwidth, ev, ev_lcb, tier, gate.
    """
    # Build pooling tiers counts
    strat = candidate.get("strategy", "ICT-A")
    direction = candidate.get("direction", "LONG")
    regime = candidate.get("regime", "UNKNOWN")
    liq_tier = candidate.get("liquidity_tier", "TIER1")
    # counts per tier
    def is_match(o, tier):
        if tier == "strategy_direction_regime_liquiditytier":
            return o.get("strategy")==strat and o.get("direction")==direction and o.get("regime")==regime and o.get("liquidity_tier")==liq_tier
        if tier == "strategy_direction_regime":
            return o.get("strategy")==strat and o.get("direction")==direction and o.get("regime")==regime
        if tier == "strategy_direction":
            return o.get("strategy")==strat and o.get("direction")==direction
        if tier == "pooled":
            return True
        return False
    counts_by_tier = {}
    for tier in ["strategy_direction_regime_liquiditytier","strategy_direction_regime","strategy_direction","pooled"]:
        wins, total = _group_counts(outcomes, lambda o: is_match(o, tier))
        counts_by_tier[tier] = (wins, total)
    global_wins, global_total = counts_by_tier["pooled"]
    sel = select_pooling_tier(counts_by_tier, (global_wins, global_total), prior_strength)
    tier = sel["selected_tier"]
    stats = sel["stats"]
    p_est = stats["p_est"]
    ci_halfwidth = stats["ci_halfwidth"]
    effective_train = stats["effective_train"]
    # EV from trades for this candidate's regime? Approx using outcomes for same tier
    # Filter trades for ev calc: use outcomes where win defined and matching tier if possible else pooled
    ev_trades = [ {"return_r": o.get("return_r", 1 if o.get("win")==1 else -1)} for o in outcomes if is_match(o, tier) ] or [ {"return_r": o.get("return_r", 1 if o.get("win")==1 else -1)} for o in outcomes ]
    ev_info = ev_from_trades(ev_trades, p_est, ci_halfwidth)
    # calibration: need y_true/y_prob for OOS if provided else train
    calib_src = oos_outcomes if oos_outcomes else outcomes
    # Generate y_prob as p_est repeated (since Tier A single p per tier)
    y_true = [o.get("win",0) for o in calib_src]
    y_prob = [p_est]*len(y_true)
    from gcis.probability.calibration import compute_ece
    ece = compute_ece(y_true, y_prob)
    # drift compare recent 50 vs baseline (if enough)
    drift_flag = False
    if len(calib_src) >= 100:
        recent = calib_src[-50:]
        baseline = calib_src[:-50]
        if recent and baseline:
            ece_recent = compute_ece([r.get("win",0) for r in recent], [p_est]*len(recent))
            ece_base = compute_ece([b.get("win",0) for b in baseline], [p_est]*len(baseline))
            drift_info = detect_drift(ece_recent, ece_base)
            drift_flag = drift_info["drift"]
    # gate
    train_n = effective_train
    oos_n = len(oos_outcomes) if oos_outcomes else 0
    # For Tier A gate, ci_halfwidth must be <=0.10
    gate = check_display_gate(train_n, oos_n, ci_halfwidth, ece, current_version==trained_version, drift_flag)
    # PRB-12 display logic: if gate fail => p_display None, ev N/A
    return {
        "candidate": candidate,
        "tier": tier,
        "tier_selection": sel,
        "p_est": round(p_est,4),
        "ci_halfwidth": round(ci_halfwidth,4),
        "effective_train": train_n,
        "oos_n": oos_n,
        "ece": round(ece,4),
        "ev": ev_info["ev"],
        "ev_lcb": ev_info["ev_lcb"],
        "ev_info": ev_info,
        "gate": gate,
        "drift_flag": drift_flag,
        "display": gate["display"],
        "version_match": current_version==trained_version,
        "note": "Tier A EB pooled; gate enforces 100/50/0.10/0.05/version/drift"
    }
