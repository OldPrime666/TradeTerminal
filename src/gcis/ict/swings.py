from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import pandas as pd

@dataclass
class Swing:
    swing_id: str
    symbol: str
    timeframe: str
    type: str  # HIGH LOW
    price: Decimal
    bar_time: datetime
    created_at: datetime
    confirmation_at: datetime
    left_bars: int
    right_bars: int
    strength: float  # in ATR
    status: str  # CANDIDATE CONFIRMED BROKEN INVALIDATED

def detect_swings(df: pd.DataFrame, symbol: str, timeframe: str, L=3, R=3, atr_series=None) -> List[Swing]:
    """
    Swing high at p if high[p] > high[p-k] for k=1..L (strict) and high[p] >= high[p+k] for k=1..R (non-strict)
    Swing low mirrored.
    CONFIRMED after bar p+R closes: confirmation_at = close_time(p+R)
    """
    if df is None or len(df) < L+R+1:
        return []
    swings: List[Swing] = []
    highs = df["high"].astype(float).values
    lows = df["low"].astype(float).values
    times = df["open_time"].values
    close_times = df["close_time"].values
    n = len(df)
    for p in range(L, n - R):
        # swing high
        is_high = True
        hp = highs[p]
        for k in range(1, L+1):
            if not (hp > highs[p-k]):
                is_high = False; break
        if is_high:
            for k in range(1, R+1):
                if not (hp >= highs[p+k]):
                    is_high=False; break
        if is_high:
            # first of equal highs: ensure not second equal
            # if previous bar equal and also would be high, skip second (keep first)
            # we already use strict left, so second equal won't pass
            bar_time = pd.to_datetime(times[p]).to_pydatetime()
            confirmation_at = pd.to_datetime(close_times[p+R]).to_pydatetime()
            created_at = confirmation_at
            # strength in ATR at confirmation
            strength = 0.0
            if atr_series is not None and len(atr_series) > p+R:
                atr = float(atr_series.iloc[p+R]) if not pd.isna(atr_series.iloc[p+R]) else 1.0
                # prominence = hp - max neighbor highs
                neigh_max = max(max(highs[p-L:p]), max(highs[p+1:p+R+1])) if p-L>=0 else hp
                strength = (hp - neigh_max) / atr if atr!=0 else 0
            swing = Swing(swing_id=f"{symbol}-{timeframe}-H-{p}", symbol=symbol, timeframe=timeframe, type="HIGH", price=Decimal(str(hp)), bar_time=bar_time, created_at=created_at, confirmation_at=confirmation_at, left_bars=L, right_bars=R, strength=strength, status="CONFIRMED")
            swings.append(swing)
        # swing low
        is_low = True
        lp = lows[p]
        for k in range(1, L+1):
            if not (lp < lows[p-k]):
                is_low=False; break
        if is_low:
            for k in range(1, R+1):
                if not (lp <= lows[p+k]):
                    is_low=False; break
        if is_low:
            bar_time = pd.to_datetime(times[p]).to_pydatetime()
            confirmation_at = pd.to_datetime(close_times[p+R]).to_pydatetime()
            created_at = confirmation_at
            strength=0.0
            if atr_series is not None and len(atr_series) > p+R:
                atr = float(atr_series.iloc[p+R]) if not pd.isna(atr_series.iloc[p+R]) else 1.0
                neigh_min = min(min(lows[p-L:p]), min(lows[p+1:p+R+1])) if p-L>=0 else lp
                strength = (neigh_min - lp) / atr if atr!=0 else 0
                strength = abs(strength)
            swing = Swing(swing_id=f"{symbol}-{timeframe}-L-{p}", symbol=symbol, timeframe=timeframe, type="LOW", price=Decimal(str(lp)), bar_time=bar_time, created_at=created_at, confirmation_at=confirmation_at, left_bars=L, right_bars=R, strength=strength, status="CONFIRMED")
            swings.append(swing)
    # mark BROKEN later by structure logic; for now CONFIRMED
    return swings
