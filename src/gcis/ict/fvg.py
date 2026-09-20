from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List
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

def detect_fvgs(df: pd.DataFrame, symbol: str, timeframe: str, atr_series, cfg: dict, displacement_indices=None) -> List[FVG]:
    """
    Bullish FVG on candles (i-2,i-1,i) if low[i] > high[i-2]
    Zone [high[i-2], low[i]]
    Qualify only if size >= max(min_size_atr*ATR, min_ticks*tick) and middle is displacement (default)
    """
    if df is None or len(df) < 3:
        return []
    fvgs=[]
    tick = 0.01  # should come from universe; use default
    # try to get tick from config
    min_size_atr = cfg.get("min_size_atr", 0.15)
    min_ticks = cfg.get("min_size_ticks", 2)
    for i in range(2, len(df)):
        # need ATR at i
        atr = float(atr_series.iloc[i]) if atr_series is not None and not pd.isna(atr_series.iloc[i]) else 1.0
        high_im2 = float(df.iloc[i-2]["high"])
        low_i = float(df.iloc[i]["low"])
        high_i2 = high_im2
        # bullish
        if low_i > high_im2:
            gap = low_i - high_im2
            min_size = max(min_size_atr * atr, min_ticks * tick)
            if gap >= min_size:
                if displacement_indices is not None:
                    if (i-1) not in displacement_indices:
                        continue
                # need displacement check already done; else skip requiring
                upper = Decimal(str(low_i))
                lower = Decimal(str(high_im2))
                mid = Decimal(str((low_i + high_im2)/2))
                created_at = pd.to_datetime(df.iloc[i]["close_time"]).to_pydatetime()
                fvgs.append(FVG(fvg_id=f"{symbol}-{timeframe}-fvgB-{i}", symbol=symbol, timeframe=timeframe, direction="BULL", upper=upper, lower=lower, midpoint=mid, created_at=created_at, status="FRESH", size_atr=gap/atr if atr else 0))
        # bearish
        high_i = float(df.iloc[i]["high"])
        low_im2 = float(df.iloc[i-2]["low"])
        if high_i < low_im2:
            gap = low_im2 - high_i
            min_size = max(min_size_atr * atr, min_ticks * tick)
            if gap >= min_size:
                if displacement_indices is not None:
                    if (i-1) not in displacement_indices:
                        continue
                upper = Decimal(str(low_im2))
                lower = Decimal(str(high_i))
                mid = Decimal(str((low_im2 + high_i)/2))
                created_at = pd.to_datetime(df.iloc[i]["close_time"]).to_pydatetime()
                fvgs.append(FVG(fvg_id=f"{symbol}-{timeframe}-fvgS-{i}", symbol=symbol, timeframe=timeframe, direction="BEAR", upper=upper, lower=lower, midpoint=mid, created_at=created_at, status="FRESH", size_atr=gap/atr if atr else 0))
    return fvgs
