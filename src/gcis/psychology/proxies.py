"""
PSY-01 proxies — sentiment proxies from price action (free-only, no key).
Initially: fear/greed via volatility, return skew, drawdown proxy, volume spike.
Deterministic, no external fetch in P15 (alternative_me deferred).
"""
from typing import Dict, Any, List
import math
import statistics

def compute_psy_proxies(closes: List[float], volumes: List[float] | None = None, period: int = 20) -> Dict[str, Any]:
    """
    closes: list of close prices (float)
    volumes: optional list same length
    Returns proxies: volatility (annualized approx), return_skew, drawdown, fear_greed (0-100), regime.
    Fear high when volatility high + negative skew + drawdown deep.
    """
    if not closes or len(closes) < period+5:
        return {"status":"INSUFFICIENT_HISTORY","fear_greed":50,"volatility":None,"note":"need >=25 closes"}
    # returns
    rets = []
    for i in range(1,len(closes)):
        if closes[i-1]==0:
            rets.append(0.0)
        else:
            rets.append(closes[i]/closes[i-1]-1)
    # volatility: std of returns * sqrt(365*24*60/15) approx but keep simple std
    recent = rets[-period:]
    vol = statistics.pstdev(recent) if len(recent)>1 else 0.0
    # annualized approx 15m bars: 365*24*4 =35136 1h? For 15m 35040 per year; use 35040
    ann_vol = vol * math.sqrt(35040) if vol else 0.0
    # skew: mean vs median? Use simple mean of rets sign
    mean_ret = statistics.mean(recent) if recent else 0
    # skew proxy: proportion of negative returns
    neg_ratio = sum(1 for r in recent if r<0)/len(recent) if recent else 0.5
    # drawdown: max peak to trough on closes
    peak = closes[0]
    max_dd = 0.0
    cur_peak = closes[0]
    for p in closes[-period:]:
        if p > cur_peak:
            cur_peak = p
        dd = (cur_peak - p)/cur_peak if cur_peak else 0
        if dd > max_dd:
            max_dd = dd
    # fear greed 0-100: 50 neutral, fear when vol high + neg_ratio high + dd high
    # Map: fear component = vol*1000 (scale), neg_ratio*30, dd*100
    fear = 0
    fear += min(vol*5000, 30)  # vol 0.006 =>30
    fear += neg_ratio * 30
    fear += min(max_dd*100*0.4, 40)  # dd 10% =>4
    fear = max(0, min(100, 50 + fear - 30))  # center 50
    # inverse for greed when positive skew
    if mean_ret > 0 and neg_ratio <0.4 and max_dd <0.03:
        fear = max(0, fear - 15)
    greed = 100 - fear
    # regime proxy for psy: high fear + high vol => risk_off
    if fear > 70 and ann_vol > 0.8:
        psy_regime = "RISK_OFF"
    elif fear < 30 and ann_vol < 0.5:
        psy_regime = "RISK_ON"
    else:
        psy_regime = "NEUTRAL"
    # volume spike proxy if volumes provided
    vol_spike = None
    if volumes and len(volumes) >= period:
        recent_vol = volumes[-period:]
        avg_vol = statistics.mean(recent_vol[:-1]) if len(recent_vol)>1 else recent_vol[-1]
        cur_vol = recent_vol[-1]
        vol_spike = cur_vol / avg_vol if avg_vol else 1.0
    return {
        "status":"OK",
        "fear_greed": round(float(fear),1),
        "greed": round(float(greed),1),
        "volatility": round(float(vol),6),
        "ann_volatility": round(float(ann_vol),4),
        "neg_ratio": round(float(neg_ratio),3),
        "max_drawdown": round(float(max_dd),4),
        "psy_regime": psy_regime,
        "vol_spike": round(float(vol_spike),3) if vol_spike is not None else None,
        "note": "PSY-01 proxies from price action; alternative_me Fear&Greed deferred"
    }

def psy_veto(fear_greed: float, psy_regime: str, config: dict | None =None) -> Dict[str,Any]:
    """
    Optional veto: block entries when RISK_OFF and fear extreme? Config-driven.
    For P15, just advisory: RISK_OFF doesn't block, but logs.
    """
    blocked=False
    reason=None
    if psy_regime=="RISK_OFF" and fear_greed > 85:
        # Could block per config, but for P15 paper not blocking per probability required_for_execution paper false
        blocked=False
        reason="PSY_RISK_OFF_EXTREME_BUT_NOT_BLOCKING_PAPER"
    return {"blocked": blocked, "reason": reason, "psy_regime": psy_regime, "fear_greed": fear_greed}
