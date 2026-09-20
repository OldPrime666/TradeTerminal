"""
ICT-08 Breaker Blocks — causal
Config: breaker.lookahead_bars 50

Definition:
  Breaker is a failed OB that after mitigation is broken by price through the opposite side with displacement.
  Example bullish OB (demand) that gets mitigated then price closes below it with bearish displacement → becomes bearish breaker (supply).
  Conversely bearish OB becomes bullish breaker.

  Simplified detection:
   - Input: list of OrderBlocks with mitigation_state, df, atr, displacement
   - For each OB that is MITIGATED (or TOUCHED), look ahead up to lookahead_bars after mitigation touch.
     If price closes beyond opposite side of OB zone by buffer (0.10 ATR) with displacement, then that OB is considered broken → breaker formed.
     Breaker zone is the OB zone flipped? In ICT, breaker zone is the OB's zone that now acts as resistance/support.
     We emit a Breaker object.

  Causal: only looks ahead; breaker confirmed when break close + displacement.

  No repaint: breaker once formed stays.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List
import pandas as pd

@dataclass
class BreakerBlock:
    breaker_id: str
    symbol: str
    timeframe: str
    direction: str  # BULL BEAR (direction of breaker: price will respect opposite)
    source_ob_id: str
    zone_high: Decimal
    zone_low: Decimal
    break_time: datetime
    status: str  # ACTIVE MITIGATED INVALIDATED

def detect_breakers(
    order_blocks: List,
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    atr_series,
    displacement_indices=None,
    cfg: dict = None,
) -> List[BreakerBlock]:
    if cfg is None:
        cfg = {}
    lookahead = cfg.get("lookahead_bars", 50)
    min_break_atr = cfg.get("min_break_atr", 0.10)
    breakers: List[BreakerBlock] = []
    disp_set = set(displacement_indices) if displacement_indices is not None else None
    # map ob mitigation index: need to find when OB was touched/mitigated
    # For simplicity, we look from ob.break_index+1 onward for a break that penetrates OB opposite side
    # Only consider OBs that have been touched/mitigated? But we can also detect break even if not yet mitigated: a fresh OB that is broken without mitigation is a breaker
    for ob in order_blocks:
        # Only consider OBs not already invalidated
        if ob.mitigation_state == "INVALIDATED":
            continue
        start = ob.break_index + 1
        if start >= len(df):
            continue
        end = min(len(df), start + lookahead)
        zl = float(ob.zone_low)
        zh = float(ob.zone_high)
        # Determine break condition opposite to OB direction
        # Bullish OB (support) -> break is bearish close below zone low - buffer
        # Bearish OB (resistance) -> break is bullish close above zone high + buffer
        found_break_idx = None
        for i in range(start, end):
            row = df.iloc[i]
            close = float(row["close"])
            atr = float(atr_series.iloc[i]) if atr_series is not None and i < len(atr_series) and not pd.isna(atr_series.iloc[i]) else 1.0
            buffer = min_break_atr * atr
            if ob.direction == "BULL":
                # look for bearish displacement break below zl
                if close < zl - buffer:
                    # require displacement (bearish) within this bar or next 2?
                    is_disp = False
                    if disp_set is not None:
                        if i in disp_set:
                            is_disp = True
                        else:
                            # check displacement in next 2?
                            for kk in range(1, 3):
                                if i + kk < len(df) and (i + kk) in disp_set:
                                    is_disp = True
                                    break
                    else:
                        is_disp = True
                    if is_disp:
                        found_break_idx = i
                        break
            else:  # BEAR
                if close > zh + buffer:
                    is_disp = False
                    if disp_set is not None:
                        if i in disp_set:
                            is_disp = True
                        else:
                            for kk in range(1, 3):
                                if i + kk < len(df) and (i + kk) in disp_set:
                                    is_disp = True
                                    break
                    else:
                        is_disp = True
                    if is_disp:
                        found_break_idx = i
                        break
        if found_break_idx is not None:
            break_time = pd.to_datetime(df.iloc[found_break_idx]["close_time"]).to_pydatetime()
            # Breaker direction opposite to source OB? Actually breaker flips: bull OB broken becomes bear breaker
            breaker_dir = "BEAR" if ob.direction == "BULL" else "BULL"
            breakers.append(
                BreakerBlock(
                    breaker_id=f"{symbol}-{timeframe}-breaker-{ob.ob_id}-{found_break_idx}",
                    symbol=symbol,
                    timeframe=timeframe,
                    direction=breaker_dir,
                    source_ob_id=ob.ob_id,
                    zone_high=Decimal(str(zh)),
                    zone_low=Decimal(str(zl)),
                    break_time=break_time,
                    status="ACTIVE",
                )
            )
    return breakers
