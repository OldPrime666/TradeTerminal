"""
ICT-03 Displacement — causal
Config (ict.displacement):
  body_to_range_min 0.60
  range_atr_min 1.5
  close_position_min 0.70
  min_consecutive 1
Definition:
  bullish displacement: body/range >=0.60 AND range >=1.5*ATR AND close in upper 70% of range [(close-low)/range >=0.70]
  bearish: same but close in lower 30% [(high-close)/range >=0.70]  i.e. close near low
  Range = high-low, body = |close-open|
  ATR fallback 1.0 if NaN
  Causal: only current bar. No repaint.
"""
import pandas as pd
from decimal import Decimal

def is_displacement(candle: dict, atr: float, cfg: dict) -> bool:
    open_ = float(candle["open"])
    close = float(candle["close"])
    high = float(candle["high"])
    low = float(candle["low"])
    rng = high - low
    if rng <= 0:
        return False
    body = abs(close - open_)
    body_ratio = body / rng
    min_body_ratio = cfg.get("body_to_range_min", 0.60)
    min_range_atr = cfg.get("range_atr_min", 1.5)
    close_pos_min = cfg.get("close_position_min", 0.70)
    if atr is None or atr == 0:
        atr = 1.0
    # threshold checks
    if body_ratio < min_body_ratio:
        return False
    if rng < min_range_atr * atr:
        return False
    # close position
    bullish = close > open_
    if bullish:
        close_pos = (close - low) / rng if rng else 0
        if close_pos < close_pos_min:
            return False
    else:
        # bearish: close near low -> high-close proximity
        # for bearish we expect close near low, so (high-close)/rng is small? Actually bearish close near low => (close-low)/rng small, (high-close)/rng large.
        # spec says close_position_min 0.70 means close within 30% of extreme.
        # For bearish we check (high-close)/range? No that would be distance from high. Bearish close near low => close is low, so (high-close)/range ~1 (large).
        # To unify, bearish displacement requires (high-close)/rng <0.30? Let's interpret: close in lower 30% => (close-low)/rng <=0.30 => equivalently (high-close)/rng >=0.70
        close_pos_bear = (high - close) / rng if rng else 0
        # Actually we want close near low, so closeness to low small => use complement. Simpler: require (close-low)/rng <= 0.30
        # Which is same as (high-close)/rng >=0.70. So check that.
        if close_pos_bear < close_pos_min:
            return False
    return True

def find_displacements(df: pd.DataFrame, atr_series, cfg: dict):
    """
    Returns list of indices i where displacement occurs (causal, only bar i).
    cfg may be empty → uses defaults above matching config/default.yaml
    """
    if cfg is None:
        cfg = {}
    # fill defaults to match default.yaml if not provided
    defaults = {"body_to_range_min": 0.60, "range_atr_min": 1.5, "close_position_min": 0.70, "min_consecutive": 1}
    for k,v in defaults.items():
        cfg.setdefault(k, v)
    res = []
    min_consec = cfg.get("min_consecutive", 1)
    # simple single-bar detection; if min_consecutive>1 require streak
    streak = 0
    for i, row in df.iterrows():
        atr = float(atr_series.iloc[i]) if atr_series is not None and i < len(atr_series) and not pd.isna(atr_series.iloc[i]) else 1.0
        # row may be dict-like with Decimal values
        candle = {"open": row["open"], "close": row["close"], "high": row["high"], "low": row["low"]}
        is_disp = is_displacement(candle, atr, cfg)
        if is_disp:
            streak += 1
            if streak >= min_consec:
                res.append(i)
        else:
            streak = 0
    return res
