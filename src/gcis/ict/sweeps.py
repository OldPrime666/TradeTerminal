from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List
import pandas as pd

@dataclass
class LiquidityLevel:
    price: Decimal
    type: str  # EQUAL_HIGH, SWING_HIGH, PDH etc
    touches: int

@dataclass
class Sweep:
    sweep_id: str
    symbol: str
    timeframe: str
    level: Decimal
    direction: str  # BULL sweep of lows / BEAR sweep of highs
    penetration: float
    sweep_time: datetime
    confirmation_status: str  # CONFIRMED vs BREAKOUT
    displacement_after: bool

def detect_sweeps(df: pd.DataFrame, symbol: str, timeframe: str, atr_series, cfg: dict, displacement_indices=None) -> List[Sweep]:
    """
    Sweep: wick penetrates level by >= min_penetration_atr*ATR and closes back inside within reject_within_bars, followed by displacement within displacement_within_bars → CONFIRMED.
    Simplified: look for swing levels, then find wick penetration + close back inside + displacement.
    """
    if df is None or len(df) < 10:
        return []
    # Use recent swing levels: previous day high/low or equal highs approximated by rolling max
    # Simplified: take recent 20 bars high/low as levels
    sweeps=[]
    min_pen_atr = cfg.get("penetration_min_atr", 0.05)
    reject_within = cfg.get("reject_within_bars", 3)
    require_disp = cfg.get("require_displacement", True)
    # Build levels from recent confirmed swings or just recent highs
    # For demo, use rolling levels: lookback 20, find local max/min levels
    # We'll treat each bar's high as potential equal high if within tolerance missed; instead use last 20 bar's max high as level
    # Iterate each bar as potential sweep candidate
    for i in range(20, len(df)):
        atr = float(atr_series.iloc[i]) if atr_series is not None and not pd.isna(atr_series.iloc[i]) else 1.0
        pen_min = min_pen_atr * atr
        # level = max high of previous 20 bars excluding current
        prev_slice = df.iloc[i-20:i]
        level_high = float(prev_slice["high"].max())
        level_low = float(prev_slice["low"].min())
        row = df.iloc[i]
        high = float(row["high"]); low = float(row["low"]); close = float(row["close"])
        # sweep of highs (bearish liquidity sweep - price goes above then closes back)
        if high > level_high + pen_min:
            penetration = high - level_high
            # need close back inside
            if close < level_high:
                # check displacement within next 3 bars
                has_disp = False
                if displacement_indices is not None:
                    for k in range(1, 4):
                        if i+k < len(df) and (i+k) in displacement_indices:
                            has_disp = True
                            break
                else:
                    has_disp = True
                if not require_disp or has_disp:
                    sweeps.append(Sweep(sweep_id=f"{symbol}-{timeframe}-sweepH-{i}", symbol=symbol, timeframe=timeframe, level=Decimal(str(level_high)), direction="BEAR", penetration=penetration, sweep_time=pd.to_datetime(row["close_time"]).to_pydatetime(), confirmation_status="CONFIRMED", displacement_after=has_disp))
        # sweep of lows (bullish - sell side liquidity)
        if low < level_low - pen_min:
            penetration = level_low - low
            if close > level_low:
                has_disp = False
                if displacement_indices is not None:
                    for k in range(1, 4):
                        if i+k < len(df) and (i+k) in displacement_indices:
                            has_disp=True; break
                else:
                    has_disp=True
                if not require_disp or has_disp:
                    sweeps.append(Sweep(sweep_id=f"{symbol}-{timeframe}-sweepL-{i}", symbol=symbol, timeframe=timeframe, level=Decimal(str(level_low)), direction="BULL", penetration=penetration, sweep_time=pd.to_datetime(row["close_time"]).to_pydatetime(), confirmation_status="CONFIRMED", displacement_after=has_disp))
    return sweeps
