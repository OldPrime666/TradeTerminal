"""
PRB Tier A Empirical Bayes Beta-Binomial — pooled shrinkage.
Config: probability.tier_a.estimator empirical_bayes_beta_binomial, pooling [strategy_direction_regime_liquiditytier, ...], prior_strength_events 20
Deterministic, no external ML.
"""
import math
from typing import List, Dict, Any, Tuple

def fit_beta_prior(pooled_wins: int, pooled_total: int, prior_strength: int = 20) -> Tuple[float, float]:
    """
    Method-of-moments prior: p = wins/total, alpha = p*strength, beta = (1-p)*strength
    Clamped to avoid 0. If total==0, use 0.5 uniform.
    """
    if pooled_total <= 0:
        p = 0.5
    else:
        p = pooled_wins / pooled_total
        p = min(max(p, 0.05), 0.95)  # clamp to avoid degenerate
    alpha = p * prior_strength
    beta = (1 - p) * prior_strength
    # ensure at least 0.5
    alpha = max(alpha, 0.5)
    beta = max(beta, 0.5)
    return float(alpha), float(beta)

def posterior_stats(group_wins: int, group_total: int, alpha: float, beta: float) -> Dict[str, float]:
    """
    Posterior Beta(wins+alpha, losses+beta). Return mean, variance, and Wilson-like CI halfwidth approx.
    Posterior mean = (wins+alpha)/(total+alpha+beta)
    Variance = alpha'*beta' / ((alpha'+beta')^2 * (alpha'+beta'+1))
    CI halfwidth approx 1.96* sqrt(var) for reporting; P13 gate uses max_ci_halfwidth 0.10 on this.
    """
    if group_total < 0:
        group_total = 0
    wins = max(group_wins, 0)
    total = max(group_total, 0)
    losses = total - wins
    a_post = wins + alpha
    b_post = losses + beta
    n_post = a_post + b_post
    mean = a_post / n_post if n_post else 0.5
    var = (a_post * b_post) / (n_post**2 * (n_post + 1)) if n_post else 0.25
    std = math.sqrt(var)
    halfwidth = 1.96 * std  # 95% CI halfwidth
    # Effective train events approximated as n_post - prior_strength? But gate uses effective train = group_total weighted by shrinkage?
    # Simplistic: effective = group_total (if >50) else shrinkage: group_total * (group_total / (group_total+prior_strength)) + prior * ...
    return {
        "alpha_post": a_post,
        "beta_post": b_post,
        "mean": mean,
        "variance": var,
        "ci_halfwidth": halfwidth,
        "n_post": n_post,
        "wins": wins,
        "total": total,
    }

def pooled_shrinkage(group_wins: int, group_total: int, global_wins: int, global_total: int, prior_strength: int = 20) -> Dict[str, float]:
    """
    Full pooled EB: fit prior from global, compute posterior for group.
    Returns posterior mean as shrunk estimate, plus diagnostics.
    """
    alpha, beta = fit_beta_prior(global_wins, global_total, prior_strength)
    stats = posterior_stats(group_wins, group_total, alpha, beta)
    stats.update({"alpha_prior": alpha, "beta_prior": beta, "global_wins": global_wins, "global_total": global_total})
    return stats

def tier_a_predict(group_wins: int, group_total: int, global_wins: int, global_total: int, prior_strength: int = 20) -> Dict[str, Any]:
    """
    PRB-01..03 Tier A prediction: for a given pooling tier, return p_est, ci_halfwidth, tier.
    Tier selection logic (PRB-02 pooling): try most specific tier first, fall back if not enough events.
    Caller will iterate pooling levels; this is single level.
    """
    out = pooled_shrinkage(group_wins, group_total, global_wins, global_total, prior_strength)
    # map to required fields for gate
    return {
        "p_est": out["mean"],
        "ci_halfwidth": out["ci_halfwidth"],
        "alpha": out["alpha_post"],
        "beta": out["beta_post"],
        "effective_train": out["total"],  # for gate: must be >=100 per tier StrategyRegime
        "variance": out["variance"],
    }

def select_pooling_tier(counts_by_tier: Dict[str, Tuple[int,int]], global_counts: Tuple[int,int], prior_strength: int = 20, census_thresholds: Dict[str,int] | None = None):
    """
    PRB-02 pooling: ordered [strategy_direction_regime_liquiditytier, strategy_direction_regime, strategy_direction, pooled]
    Each tier has min events threshold; pick most specific that meets threshold.
    counts_by_tier: tier_name -> (wins,total). Must include pooled fallback.
    Returns selected tier name, stats, and tiers tried.
    """
    # default thresholds per tiers (from config census_thresholds)
    if census_thresholds is None:
        census_thresholds = {"tier_strategy_regime_min_events": 300, "tier_strategy_min_events": 150, "tier_pooled_min_events": 60}
    order = [
        ("strategy_direction_regime_liquiditytier", census_thresholds.get("tier_strategy_regime_min_events", 300)),
        ("strategy_direction_regime", 100),  # intermediate, not in census but for demo
        ("strategy_direction", census_thresholds.get("tier_strategy_min_events", 150)),
        ("pooled", census_thresholds.get("tier_pooled_min_events", 60)),
    ]
    global_wins, global_total = global_counts
    for tier_name, min_events in order:
        if tier_name not in counts_by_tier:
            continue
        wins, total = counts_by_tier[tier_name]
        if total >= min_events:
            stats = tier_a_predict(wins, total, global_wins, global_total, prior_strength)
            return {"selected_tier": tier_name, "stats": stats, "wins": wins, "total": total, "threshold": min_events, "fallback": False}
    # fallback to pooled even if below threshold -> but mark fallback
    wins, total = counts_by_tier.get("pooled", (global_wins, global_total))
    stats = tier_a_predict(wins, total, global_wins, global_total, prior_strength)
    return {"selected_tier": "pooled", "stats": stats, "wins": wins, "total": total, "threshold": census_thresholds.get("tier_pooled_min_events",60), "fallback": True, "note": "FALLBACK_BELOW_THRESHOLD"}
