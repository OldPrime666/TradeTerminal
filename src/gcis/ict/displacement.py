import pandas as pd
from decimal import Decimal

def is_displacement(candle: dict, atr: float, cfg: dict) -> bool:
    """
    Displacement if body/range >= min_body_ratio and range >= min_range_atr * ATR
    Or cluster (handled externally).
    """
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
    if body_ratio >= min_body_ratio and rng >= min_range_atr * atr:
        return True
    return False

def find_displacements(df: pd.DataFrame, atr_series, cfg: dict):
    res = []
    for i, row in df.iterrows():
        atr = float(atr_series.iloc[i]) if atr_series is not None and not pd.isna(atr_series.iloc[i]) else 1.0
        if is_displacement(row, atr, cfg):
            res.append(i)
    return res
