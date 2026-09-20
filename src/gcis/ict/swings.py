"""
ICT-01 Swings — causal, deterministic, no-repaint
Spec (config/default.yaml ict.swing):
  L=R=3, min_strength_atr=0.5, min_separation_bars=3
Definition:
  Swing HIGH at pivot p iff high[p] > high[p-k] for k=1..L (strict) and
                         high[p] >= high[p+k] for k=1..R (non-strict)
  Swing LOW mirrored: low[p] < low[p-k] strict left, <= right
  CONFIRMED after bar p+R closes → confirmation_at = close_time[p+R] (causal)
  strength = (hp - max(neighbour highs)) / ATR@confirmation  (ATR Wilder 14)
             for lows (min_neighbour - lp)/ATR abs
  Filtering:
    - if ATR available (not NaN) and strength < min_strength_atr → skip
      (when ATR NaN (warmup) filter is skipped to keep warmup swings)
    - min_separation_bars: pivots within 3 bars are not independent;
      causal keep-first: iterate swings by confirmation_at; keep swing only
      if its pivot index distance > min_separation to any previously kept
      swing of same type. Later weaker within window is discarded (no repaint
      of previously confirmed swing).
  No future bar beyond p+R is used. No repaint: confirmed swing never removed
  due to future data (separation keeps first, BOS marks BROKEN but does not
  delete).
"""
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

def detect_swings(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    L=3,
    R=3,
    atr_series=None,
    min_strength_atr: float = 0.5,
    min_separation_bars: int = 3,
) -> List[Swing]:
    """
    Causal swing detection. Only bars up to p+R are used to confirm pivot p.
    Deterministic: same df → same swings. No repaint: prefix swings are subset
    of full. Implements ICT-01 thresholds.
    """
    if df is None or len(df) < L + R + 1:
        return []
    # allow config override via caller passing explicit cfg values
    swings: List[Swing] = []
    highs = df["high"].astype(float).values
    lows = df["low"].astype(float).values
    times = df["open_time"].values
    close_times = df["close_time"].values
    n = len(df)
    for p in range(L, n - R):
        # --- swing high ---
        is_high = True
        hp = highs[p]
        for k in range(1, L + 1):
            if not (hp > highs[p - k]):
                is_high = False
                break
        if is_high:
            for k in range(1, R + 1):
                if not (hp >= highs[p + k]):
                    is_high = False
                    break
        if is_high:
            bar_time = pd.to_datetime(times[p]).to_pydatetime()
            confirmation_at = pd.to_datetime(close_times[p + R]).to_pydatetime()
            created_at = confirmation_at
            strength = 0.0
            atr_val = None
            if atr_series is not None and len(atr_series) > p + R:
                v = atr_series.iloc[p + R]
                if not pd.isna(v):
                    atr_val = float(v)
                    neigh_max = max(float(max(highs[p - L:p])), float(max(highs[p + 1:p + R + 1])))
                    strength = (hp - neigh_max) / atr_val if atr_val != 0 else 0
                else:
                    # warmup → strength 0 but skip filter (keep swing)
                    # still compute with fallback 1 for reporting
                    neigh_max = max(float(max(highs[p - L:p])), float(max(highs[p + 1:p + R + 1])))
                    strength = (hp - neigh_max) / 1.0
            else:
                # no ATR → fallback 1 for strength reporting
                neigh_max = max(float(max(highs[p - L:p])), float(max(highs[p + 1:p + R + 1])))
                strength = (hp - neigh_max) / 1.0
            # filter by min_strength only when ATR was valid
            if atr_val is not None and strength < min_strength_atr:
                pass
            else:
                swing = Swing(
                    swing_id=f"{symbol}-{timeframe}-H-{p}",
                    symbol=symbol,
                    timeframe=timeframe,
                    type="HIGH",
                    price=Decimal(str(hp)),
                    bar_time=bar_time,
                    created_at=created_at,
                    confirmation_at=confirmation_at,
                    left_bars=L,
                    right_bars=R,
                    strength=strength,
                    status="CONFIRMED",
                )
                swings.append(swing)
        # --- swing low ---
        is_low = True
        lp = lows[p]
        for k in range(1, L + 1):
            if not (lp < lows[p - k]):
                is_low = False
                break
        if is_low:
            for k in range(1, R + 1):
                if not (lp <= lows[p + k]):
                    is_low = False
                    break
        if is_low:
            bar_time = pd.to_datetime(times[p]).to_pydatetime()
            confirmation_at = pd.to_datetime(close_times[p + R]).to_pydatetime()
            created_at = confirmation_at
            strength = 0.0
            atr_val = None
            if atr_series is not None and len(atr_series) > p + R:
                v = atr_series.iloc[p + R]
                if not pd.isna(v):
                    atr_val = float(v)
                    neigh_min = min(float(min(lows[p - L:p])), float(min(lows[p + 1:p + R + 1])))
                    strength = (neigh_min - lp) / atr_val if atr_val != 0 else 0
                    strength = abs(strength)
                else:
                    neigh_min = min(float(min(lows[p - L:p])), float(min(lows[p + 1:p + R + 1])))
                    strength = abs((neigh_min - lp) / 1.0)
            else:
                neigh_min = min(float(min(lows[p - L:p])), float(min(lows[p + 1:p + R + 1])))
                strength = abs((neigh_min - lp) / 1.0)
            if atr_val is not None and strength < min_strength_atr:
                pass
            else:
                swing = Swing(
                    swing_id=f"{symbol}-{timeframe}-L-{p}",
                    symbol=symbol,
                    timeframe=timeframe,
                    type="LOW",
                    price=Decimal(str(lp)),
                    bar_time=bar_time,
                    created_at=created_at,
                    confirmation_at=confirmation_at,
                    left_bars=L,
                    right_bars=R,
                    strength=strength,
                    status="CONFIRMED",
                )
                swings.append(swing)

    # min_separation_bars — causal keep-first per type
    if min_separation_bars and min_separation_bars > 0:
        # sort by confirmation time (causal order)
        swings_sorted = sorted(swings, key=lambda s: (s.confirmation_at, s.bar_time))
        kept: List[Swing] = []
        kept_pivots_high = []  # list of (pivot_idx, swing)
        kept_pivots_low = []
        # need pivot index from swing_id suffix
        for s in swings_sorted:
            try:
                p_idx = int(s.swing_id.split("-")[-1])
            except:
                p_idx = 0
            if s.type == "HIGH":
                too_close = any(abs(p_idx - pp) < min_separation_bars for pp in kept_pivots_high)
                if too_close:
                    continue
                kept.append(s)
                kept_pivots_high.append(p_idx)
            else:
                too_close = any(abs(p_idx - pp) < min_separation_bars for pp in kept_pivots_low)
                if too_close:
                    continue
                kept.append(s)
                kept_pivots_low.append(p_idx)
        # re-sort by bar_time for output stability
        kept_sorted = sorted(kept, key=lambda s: s.bar_time)
        return kept_sorted
    return sorted(swings, key=lambda s: s.bar_time)
