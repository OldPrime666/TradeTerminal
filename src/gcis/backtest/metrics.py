"""
Metrics BKT-08 — 365d window, shared-core metrics.

Computes win_rate, expectancy, pf, max_dd, sharpe-like, etc. deterministically.
All numerics use Decimal for PnL, float for aggregates.

Annualization: 365 days per backtest.annualization_days.
"""
from decimal import Decimal, getcontext
from typing import List, Dict, Any
import math

getcontext().prec = 28

def compute_metrics(trades: List[Dict[str, Any]], bars: int = 0, timeframe: str = "15m", annualization_days: int = 365) -> Dict[str, Any]:
    """
    trades: list of dicts with keys: pnl (Decimal or float), net_pnl, return_r, win (bool), entry_time, exit_time
    Returns metrics dict with 365d annualization where applicable.
    If no trades, return INSUFFICIENT.
    """
    if not trades:
        return {
            "bars": bars,
            "trades": 0,
            "win_rate": None,
            "avg_win": None,
            "avg_loss": None,
            "expectancy": None,
            "profit_factor": None,
            "max_drawdown": None,
            "sharpe_like": None,
            "total_net_pnl": "0",
            "total_return_r": "0",
            "status": "INSUFFICIENT_TRADES",
            "window_days": annualization_days,
            "timeframe": timeframe,
        }
    # Normalize pnls
    pnls = []
    for t in trades:
        v = t.get("net_pnl", t.get("pnl", 0))
        if isinstance(v, Decimal):
            pnls.append(float(v))
        elif isinstance(v, str):
            try:
                pnls.append(float(Decimal(v)))
            except:
                pnls.append(0.0)
        else:
            pnls.append(float(v))
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    total = len(pnls)
    win_rate = len(wins) / total if total else None
    avg_win = sum(wins)/len(wins) if wins else None
    avg_loss = sum(losses)/len(losses) if losses else None
    # expectancy in R or pnl units
    expectancy = sum(pnls)/total if total else None
    gross_win = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = (gross_win / gross_loss) if gross_loss != 0 else (float('inf') if gross_win>0 else None)
    # max drawdown: cumulative sum then max peak-to-trough
    cum = 0
    peak = 0
    max_dd = 0
    for p in pnls:
        cum += p
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > max_dd:
            max_dd = dd
    # sharpe-like: mean / std * sqrt(annualized trades? approx)
    if len(pnls) > 1:
        mean = sum(pnls)/len(pnls)
        var = sum((x-mean)**2 for x in pnls)/ (len(pnls)-1)
        std = math.sqrt(var) if var>0 else 0
        sharpe = (mean / std * math.sqrt(365*24*60 / 15) ) if std else None  # approx 365d 15m bars ~ 35040
        # For generic timeframe, approximate bars per year
    else:
        sharpe = None
    total_net = sum(pnls)
    # return_r sum if available
    total_r = 0.0
    for t in trades:
        rr = t.get("return_r")
        if rr is not None:
            try:
                total_r += float(rr)
            except:
                pass
    return {
        "bars": bars,
        "trades": total,
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "avg_win": round(avg_win, 4) if avg_win is not None else None,
        "avg_loss": round(avg_loss, 4) if avg_loss is not None else None,
        "expectancy": round(expectancy, 4) if expectancy is not None else None,
        "profit_factor": round(profit_factor, 4) if isinstance(profit_factor, float) and math.isfinite(profit_factor) else profit_factor,
        "max_drawdown": round(max_dd, 4),
        "sharpe_like": round(sharpe, 4) if sharpe is not None and math.isfinite(sharpe) else None,
        "total_net_pnl": str(round(total_net, 4)),
        "total_return_r": str(round(total_r, 4)),
        "status": "OK" if total >= 30 else "DEGRADED_SMALL_SAMPLE",
        "window_days": annualization_days,
        "timeframe": timeframe,
    }

def compute_365d_slice(trades: List[Dict[str, Any]], days: int = 365) -> Dict[str, Any]:
    """Stub for 365d rolling — for P08 we just delegate to compute_metrics with annualization."""
    return compute_metrics(trades, bars=len(trades), annualization_days=days)
