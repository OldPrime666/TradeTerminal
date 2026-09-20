"""
ICT-04 FVG (Fair Value Gap) — causal, deterministic
Config (ict.fvg):
  min_size_atr 0.15
  min_size_ticks 2
  max_age_bars 200
  mitigation 50pct_or_full

Definition:
  3-bar pattern (i-2,i-1,i):
    Bullish FVG if low[i] > high[i-2] → zone [high[i-2], low[i]] (gap)
    Bearish if high[i] < low[i-2] → zone [high[i], low[i-2]]
  Qualify only if gap >= max(min_size_atr*ATR[i], min_size_ticks*tick)
  Displacement filter (ICT): middle bar i-1 must be displacement (body/range etc)
    If displacement_indices provided, require (i-1) in indices. If not provided, skip filter.
  Created after bar i closes → created_at = close_time[i] (causal)
  ICT-11 relative units: size checked in ATR/ticks not absolute
  No repaint: once created, FVG persists; mitigation status updated later by mitigation module.
  max_age_bars used by mitigation/invalidation to expire FVGs after 200 bars without mitigation.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import pandas as pd

@dataclass
class FVG:
    fvg_id: str
    symbol: str
    timeframe: str
    direction: str  # BULL BEAR
    upper: Decimal
    lower: Decimal
    midpoint: Decimal
    created_at: datetime
    status: str  # FRESH TOUCHED MITIGATED INVALIDATED
    size_atr: float
    created_index: int  # bar index of i (for age)

def detect_fvgs(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    atr_series,
    cfg: dict,
    displacement_indices=None,
) -> List[FVG]:
    if df is None or len(df) < 3:
        return []
    if cfg is None:
        cfg = {}
    cfg.setdefault("min_size_atr", 0.15)
    cfg.setdefault("min_size_ticks", 2)
    cfg.setdefault("max_age_bars", 200)
    min_size_atr = cfg.get("min_size_atr", 0.15)
    min_ticks = cfg.get("min_size_ticks", 2)
    tick = cfg.get("tick_size", 0.01)
    # tick may be Decimal; ensure float
    try:
        tick_f = float(tick)
    except:
        tick_f = 0.01
    fvgs: List[FVG] = []
    for i in range(2, len(df)):
        atr = float(atr_series.iloc[i]) if atr_series is not None and i < len(atr_series) and not pd.isna(atr_series.iloc[i]) else 1.0
        # displacement filter on middle candle i-1
        if displacement_indices is not None:
            if (i - 1) not in displacement_indices:
                # still allow if displacement_indices is empty list? spec says require displacement
                # If displacement_indices is provided and middle not displacement → skip
                # But for golden tests where displacement not computed, caller passes None
                # So we skip only when list provided and middle missing
                pass_flag = True
                # we need to check explicitly
                # The earlier code did continue; we replicate but we need to differentiate None vs []
                # We'll continue only if middle not in list
                # already above: if not in -> we want to skip FVG
                # But we prematurely continued? Let's implement correctly below
                pass
        # Actually enforce:
        if displacement_indices is not None and (i - 1) not in displacement_indices:
            # If displacement filter required but middle not displacement → not a valid institutional FVG
            # But for testing without displacement, pass None instead.
            # Here we skip
            # However if displacement_indices is empty list, we also skip all (correct)
            # We need to detect whether caller wants filtering: if list is not None, enforce.
            # So check and continue
            # But we already have logic above; we will handle here:
            # We'll redo bullish/bearish logic after this check
            # For efficiency we can set a flag
            middle_is_disp = False
        else:
            middle_is_disp = True if displacement_indices is None else True  # when not filtered, true

        # re-evaluate middle displacement requirement
        if displacement_indices is not None and (i - 1) not in displacement_indices:
            # skip this i entirely
            # But we still need to allow FVG detection if caller explicitly wants no filter (None)
            # Since displacement_indices is not None and middle missing => invalid FVG per ICT in institutions
            # Skip to next i
            # To avoid duplicate logic, we will have continue after size checks? Better continue now.
            # We'll store skip flag:
            skip_due_to_disp = True
        else:
            skip_due_to_disp = False

        # bullish
        high_im2 = float(df.iloc[i - 2]["high"])
        low_i = float(df.iloc[i]["low"])
        gap_bull = low_i - high_im2
        if gap_bull > 0:
            min_size = max(min_size_atr * atr, min_ticks * tick_f)
            if gap_bull >= min_size:
                if not skip_due_to_disp:
                    upper = Decimal(str(low_i))
                    lower = Decimal(str(high_im2))
                    mid = Decimal(str((low_i + high_im2) / 2))
                    created_at = pd.to_datetime(df.iloc[i]["close_time"]).to_pydatetime()
                    fvgs.append(
                        FVG(
                            fvg_id=f"{symbol}-{timeframe}-fvgB-{i}",
                            symbol=symbol,
                            timeframe=timeframe,
                            direction="BULL",
                            upper=upper,
                            lower=lower,
                            midpoint=mid,
                            created_at=created_at,
                            status="FRESH",
                            size_atr=gap_bull / atr if atr else 0,
                            created_index=i,
                        )
                    )
        # bearish
        high_i = float(df.iloc[i]["high"])
        low_im2 = float(df.iloc[i - 2]["low"])
        gap_bear = low_im2 - high_i
        if gap_bear > 0:
            min_size = max(min_size_atr * atr, min_ticks * tick_f)
            if gap_bear >= min_size:
                if not skip_due_to_disp:
                    upper = Decimal(str(low_im2))
                    lower = Decimal(str(high_i))
                    mid = Decimal(str((low_im2 + high_i) / 2))
                    created_at = pd.to_datetime(df.iloc[i]["close_time"]).to_pydatetime()
                    fvgs.append(
                        FVG(
                            fvg_id=f"{symbol}-{timeframe}-fvgS-{i}",
                            symbol=symbol,
                            timeframe=timeframe,
                            direction="BEAR",
                            upper=upper,
                            lower=lower,
                            midpoint=mid,
                            created_at=created_at,
                            status="FRESH",
                            size_atr=gap_bear / atr if atr else 0,
                            created_index=i,
                        )
                    )
    return fvgs
