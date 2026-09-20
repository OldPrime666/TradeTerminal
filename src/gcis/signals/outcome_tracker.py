"""
SIG-08 Outcome Tracker — every MV-pass gets net R, also risk-blocked
For every signal that passes MV gates (market validity), we record outcome with net R
even if PX (risk/duplicate/kill) blocks execution. This enables counterfactual.
Ambiguous intrabar policy: pessimistic (if both TP and SL could be hit, SL first).
BKT-01 same core, here we just compute net R label for backtest/paper.
"""
from decimal import Decimal
from typing import Dict, Optional
import math

def compute_net_r(entry: Decimal, stop: Decimal, target: Decimal, costs: Dict, direction: str = "LONG") -> Optional[float]:
    """
    Computes net R = (target - entry - costs)/(entry - stop + costs) for LONG
    For SHORT: (entry - target - costs)/(stop - entry + costs)
    Uses taker fees + slippage from costs config.
    Returns None if invalid (stop == entry).
    """
    if entry is None or stop is None or target is None:
        return None
    try:
        e = float(entry)
        s = float(stop)
        t = float(target)
    except:
        return None
    taker_bps = costs.get("taker_fee_bps", 5) if costs else 5
    slippage_bps = costs.get("slippage_bps_base", 2) if costs else 2
    total_bps = (taker_bps*2 + slippage_bps) / 10000.0
    cost = e * total_bps
    if direction == "SHORT":
        # For short, risk = stop - entry (stop above entry)
        risk = s - e
        reward = e - t
    else:
        risk = e - s
        reward = t - e
    if risk <= 0:
        return None
    # net after costs: reward - cost, risk + cost (conservative)
    net_r = (reward - cost) / (risk + cost)
    if math.isnan(net_r) or math.isinf(net_r):
        return None
    return float(net_r)

def label_outcome(mv_pass: bool, px_pass: bool, net_r: Optional[float], would_be_blocked_by_risk: bool = False) -> Dict:
    """
    Returns outcome dict with outcome label and net_r.
    outcome in: PENDING (not yet), MV_FAIL, PX_BLOCKED, FILLED, etc.
    For tracker we always produce a row when mv_pass true, with net_r computed.
    would_be_blocked_by_risk true if PX blocked due to risk (for counterfactual).
    """
    if not mv_pass:
        return {"outcome": "MV_FAIL", "net_r": None, "would_be_blocked_by_risk": False}
    # MV pass
    outcome = "PX_BLOCKED" if not px_pass else "PENDING"
    # If still pending, net_r is expected R if PX passes, otherwise counterfactual
    return {"outcome": outcome, "net_r": net_r, "would_be_blocked_by_risk": would_be_blocked_by_risk and not px_pass}

def tracker_record(signal_id: str, symbol: str, venue: str, mv_pass: bool, px_pass: bool, entry: Decimal, stop: Decimal, target: Decimal, costs: Dict, direction: str, risk_blocked: bool = False) -> Dict:
    """
    Helper to build SignalOutcome dict for DB insertion.
    Must be called for every MV pass (including risk-blocked) per SIG-08.
    """
    net_r = compute_net_r(entry, stop, target, costs, direction) if mv_pass else None
    lab = label_outcome(mv_pass, px_pass, net_r, risk_blocked)
    return {
        "signal_id": signal_id,
        "symbol": symbol,
        "venue": venue,
        "outcome": lab["outcome"],
        "net_r": Decimal(str(lab["net_r"])) if lab["net_r"] is not None else None,
        "would_be_blocked_by_risk": lab["would_be_blocked_by_risk"],
    }
