from dataclasses import dataclass
from typing import Optional
import pandas as pd
from gcis.market.indicators import adx_wilder, efficiency_ratio, bollinger, atr_wilder

@dataclass
class RegimeResult:
    trend_regime: str  # TRENDING_UP etc
    vol_regime: str    # LOW NORMAL HIGH
    flags: list
    agreement: float
    evidence: list
    valid: bool

def compute_regime(df: pd.DataFrame, config: dict) -> RegimeResult:
    """
    df columns: high, low, close, volume, close_time
    Causal only — uses only past data via rolling/ewm.
    """
    if df is None or len(df) < 30:
        return RegimeResult("UNCERTAIN","NORMAL",[],0.0,["INSUFFICIENT_HISTORY"], False)
    close = df["close"]
    high = df["high"]; low = df["low"]
    # ADX
    try:
        adx, plus_di, minus_di = adx_wilder(high, low, close, period=14)
        adx_last = float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 0
    except:
        adx_last = 0
    try:
        er = efficiency_ratio(close, period=20)
        er_last = float(er.iloc[-1]) if not pd.isna(er.iloc[-1]) else 0
    except:
        er_last = 0
    # EMA stack
    ema21 = close.ewm(span=21, adjust=False).mean().iloc[-1] if len(close)>=21 else float(close.iloc[-1])
    ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1] if len(close)>=50 else float(close.iloc[-1])
    # ATR percentile
    try:
        atr = atr_wilder(high, low, close, 14)
        atr_last = float(atr.iloc[-1])
        atr_pct = float(atr.rank(pct=True).iloc[-1]) if len(atr)>=50 else 0.5
    except:
        atr_last = 0; atr_pct = 0.5
    # BB bandwidth percentile
    try:
        _, _, _, bw = bollinger(close, 20, 2.0)
        bw_last = float(bw.iloc[-1]) if not pd.isna(bw.iloc[-1]) else 0
        bw_pct = float(bw.rank(pct=True).iloc[-1]) if len(bw)>=50 else 0.5
    except:
        bw_pct = 0.5

    evidence = []
    trend = "UNCERTAIN"
    # rules from Part12
    cfg_trend_up = config.get("regime",{}).get("trend_up", {"adx_min":22, "efficiency_ratio_min":0.30})
    cfg_trend_down = config.get("regime",{}).get("trend_down", {"adx_min":22, "efficiency_ratio_min":0.30})
    cfg_ranging = config.get("regime",{}).get("ranging", {"adx_max":18, "efficiency_ratio_max":0.25, "bb_bandwidth_percentile_max":50})

    is_up = adx_last >= cfg_trend_up.get("adx_min",22) and er_last >= cfg_trend_up.get("efficiency_ratio_min",0.30) and ema21 > ema50
    is_down = adx_last >= cfg_trend_down.get("adx_min",22) and er_last >= cfg_trend_down.get("efficiency_ratio_min",0.30) and ema21 < ema50
    is_ranging = adx_last <= cfg_ranging.get("adx_max",18) and er_last <= cfg_ranging.get("efficiency_ratio_max",0.25) and bw_pct*100 <= cfg_ranging.get("bb_bandwidth_percentile_max",50)

    if is_up and not is_down:
        trend="TRENDING_UP"; evidence.append(f"ADX {adx_last:.1f}>=22 ER {er_last:.2f} ema21>ema50")
    elif is_down and not is_up:
        trend="TRENDING_DOWN"; evidence.append(f"ADX {adx_last:.1f}>=22 ER {er_last:.2f} ema21<ema50")
    elif is_ranging:
        trend="RANGING"; evidence.append(f"ADX {adx_last:.1f}<=18 ER {er_last:.2f} BW% {bw_pct*100:.0f}")
    else:
        trend="UNCERTAIN"; evidence.append(f"conflicting: ADX {adx_last:.1f} ER {er_last:.2f}")

    # vol regime
    vol = "NORMAL"
    vol_low = config.get("regime",{}).get("vol_low_atr_percentile_max",25)
    vol_high = config.get("regime",{}).get("vol_high_atr_percentile_min",80)
    if atr_pct*100 <= vol_low:
        vol="LOW"
    elif atr_pct*100 >= vol_high:
        vol="HIGH"

    flags=[]
    # expansion/contraction
    if atr_pct*100 >= 70:
        flags.append("EXPANSION")
    if bw_pct*100 <= 20:
        flags.append("CONTRACTION")

    agreement = 1.0 if trend!="UNCERTAIN" else 0.3
    return RegimeResult(trend, vol, flags, agreement, evidence, True)
