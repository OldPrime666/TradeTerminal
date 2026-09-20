"""
BKT-11 paper-vs-backtest consistency — compare paper fills (paper.py) vs backtest engine fills (pessimistic 5bps) for divergence.
Also DAT-12:5 funding, OPS-09:6 effective leverage cluster consistency.

For P19 we provide function to compare notional PnL distributions and flag divergence beyond threshold.
"""
from typing import Dict, Any, List
import statistics

def compare_paper_backtest(paper_trades: List[Dict[str,Any]], backtest_trades: List[Dict[str,Any]], threshold_bps: float =15.0) -> Dict[str,Any]:
    """
    Compare lists of trades with keys net_pnl, entry, exit, qty.
    Returns mean divergence in bps and flag if beyond threshold.
    Deterministic.
    """
    if not paper_trades or not backtest_trades:
        return {"status":"INSUFFICIENT_DATA","divergence_bps": None, "flag": False, "note":"need both lists"}
    # Compute avg pnl per trade in bps of entry
    def avg_pnl_bps(trades):
        bps=[]
        for t in trades:
            entry = t.get("entry", t.get("price", 100))
            pnl = t.get("net_pnl", t.get("pnl", 0))
            try:
                bps.append(float(pnl)/float(entry)*10000)
            except: bps.append(0)
        return statistics.mean(bps) if bps else 0
    paper_bps = avg_pnl_bps(paper_trades)
    back_bps = avg_pnl_bps(backtest_trades)
    divergence = abs(paper_bps - back_bps)
    flag = divergence > threshold_bps
    return {
        "paper_avg_bps": round(paper_bps,2),
        "backtest_avg_bps": round(back_bps,2),
        "divergence_bps": round(divergence,2),
        "threshold_bps": threshold_bps,
        "flag": flag,
        "status": "DIVERGED" if flag else "CONSISTENT",
        "note": "BKT-11 paper-vs-backtest consistency, threshold 15 bps"
    }

def funding_consistency_check(funding_estimate: float, funding_realized: float, max_fraction_R: float =0.15) -> Dict[str,Any]:
    """
    DAT-12:5 funding too costly fraction of R: compare estimated vs realized, flag if realized > max_fraction*R
    For stub, just check ratio.
    """
    # funding_estimate in bps of notional, compare to R 100bps (1R)
    ratio = abs(funding_realized) / 100 if funding_realized else 0  # 100 bps = 1R proxy
    flag = ratio > max_fraction_R
    return {"estimate_bps": funding_estimate, "realized_bps": funding_realized, "ratio_R": round(ratio,4), "flag": flag, "max_fraction_R": max_fraction_R}

def effective_leverage_consistency(notional: float, equity: float, cap: float =3.0) -> Dict[str,Any]:
    lev = notional/equity if equity else 0
    flag = lev > cap
    return {"leverage": round(lev,3), "cap": cap, "flag": flag, "status": "EXCEEDS" if flag else "OK"}
