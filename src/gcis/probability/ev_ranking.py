"""
PRB EV and EV_lcb ranking — expected value in R, lower confidence bound.
Config: probability.ev lcb_percentile 10, min_ev_lcb_r 0.0 ; display_gate controls.
EV = p_win * avg_win_R - (1-p_win) * avg_loss_R
EV_lcb = EV - z*SE where SE estimated via bootstrap or Wilson approx on p.
For Tier A we use normal approx on p's CI halfwidth to derive EV_lcb.
 Ranking by EV_lcb, not setup_score, when gate passes.
"""
import math
from typing import List, Dict, Any, Tuple

# z for 80% one-sided ~0.84 for 10th percentile? LCB 10th => z=1.28 for 10% lower? Actually 10th percentile means 1.28 sigma below mean for normal 90% CI.
Z_10 = 1.281551565  # for 10th percentile lower bound

def compute_ev(p_win: float, avg_win_r: float, avg_loss_r: float) -> float:
    """
    avg_loss_r should be positive magnitude (e.g., 1.0 for 1R loss). p_win in [0,1].
    """
    p = min(max(p_win, 0.0), 1.0)
    win = float(avg_win_r) if avg_win_r else 0
    loss = float(avg_loss_r) if avg_loss_r else 0
    # loss is magnitude; expected loss = (1-p)*loss
    ev = p * win - (1 - p) * loss
    return float(ev)

def compute_ev_lcb(p_win: float, avg_win_r: float, avg_loss_r: float, ci_halfwidth: float, z: float = Z_10) -> float:
    """
    Lower confidence bound on EV by shifting p_win down by CI halfwidth scaled by z? Actually ci_halfwidth is 95% (1.96 sigma).
    Convert to sigma = ci_halfwidth/1.96, then lcb p = p - z*sigma, then recompute EV.
    Clamp p_lcb to [0,1].
    """
    ev = compute_ev(p_win, avg_win_r, avg_loss_r)
    # sigma from 95% halfwidth
    sigma = ci_halfwidth / 1.96 if ci_halfwidth else 0
    p_lcb = p_win - z * sigma
    p_lcb = min(max(p_lcb, 0.0), 1.0)
    ev_lcb = compute_ev(p_lcb, avg_win_r, avg_loss_r)
    return float(ev_lcb)

def ev_from_trades(trades: List[Dict[str,Any]], p_est: float, ci_halfwidth: float) -> Dict[str,float]:
    """
    Compute avg_win/avg_loss from trades list (net R). Trades assumed to have return_r or net_pnl/risk.
    For EV we need avg_win_r (mean of positive R) and avg_loss_r (mean magnitude of negative).
    Then compute ev and ev_lcb.
    """
    if not trades:
        return {"ev": 0.0, "ev_lcb": 0.0, "p_est": p_est, "avg_win_r": 0, "avg_loss_r": 0, "n":0}
    rs = []
    for t in trades:
        r = t.get("return_r", t.get("net_r", t.get("r", 0)))
        try: rs.append(float(r))
        except: rs.append(0.0)
    wins = [r for r in rs if r > 0]
    losses = [abs(r) for r in rs if r <= 0]
    avg_win = sum(wins)/len(wins) if wins else 1.0  # default 1R if no win observed? Use 1.0 to avoid zero ev artificially
    avg_loss = sum(losses)/len(losses) if losses else 1.0
    ev = compute_ev(p_est, avg_win, avg_loss)
    ev_lcb = compute_ev_lcb(p_est, avg_win, avg_loss, ci_halfwidth)
    return {"ev": round(ev,4), "ev_lcb": round(ev_lcb,4), "p_est": round(p_est,4), "avg_win_r": round(avg_win,4), "avg_loss_r": round(avg_loss,4), "n": len(rs), "ci_halfwidth": round(ci_halfwidth,4)}

def rank_by_ev_lcb(candidates: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    """
    candidates: list of dicts with keys symbol, direction, p_est, ev_lcb, setup_score etc.
    Sort descending ev_lcb. If tie, higher p_est, then setup_score.
    Returns sorted list with rank field.
    """
    def _key(c):
        return (c.get("ev_lcb", -1e9), c.get("p_est", 0), c.get("setup_score",0))
    sorted_c = sorted(candidates, key=_key, reverse=True)
    for i, c in enumerate(sorted_c):
        c["rank"] = i+1
    return sorted_c
