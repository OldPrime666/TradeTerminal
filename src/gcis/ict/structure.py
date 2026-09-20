from dataclasses import dataclass
from typing import List, Optional
from decimal import Decimal
from datetime import datetime
import pandas as pd
from gcis.ict.swings import Swing

@dataclass
class StructureEvent:
    event_id: str
    type: str  # BOS, CHOCH
    direction: str  # BULL BEAR
    broken_swing_id: str
    broken_level: Decimal
    break_bar_time: datetime
    break_price: Decimal
    bias_before: str
    bias_after: str

def detect_structure(swings: List[Swing], df: pd.DataFrame, bos_buffer_atr: float = 0.10, atr_series=None) -> tuple[List[StructureEvent], str]:
    """
    Detect BOS/CHOCH. Bias UNDEFINED until >=2 highs and >=2 lows.
    Level = latest confirmed unbroken swing high/low.
    Break if close exceeds level by bos_buffer_atr * ATR.
    """
    if not swings:
        return [], "UNDEFINED"
    # sort swings by confirmation time
    swings_sorted = sorted(swings, key=lambda s: s.confirmation_at)
    highs = [s for s in swings_sorted if s.type=="HIGH" and s.status=="CONFIRMED"]
    lows = [s for s in swings_sorted if s.type=="LOW" and s.status=="CONFIRMED"]
    bias = "UNDEFINED"
    if len(highs)>=2 and len(lows)>=2:
        # initial bias from last two swings? Simplified: if last high higher than previous high => BULLISH else BEARISH?
        # We'll start UNDEFINED then let events flip it.
        bias = "UNDEFINED"
    else:
        return [], "UNDEFINED"

    events: List[StructureEvent] = []
    broken_ids = set()
    # keep unbroken highs/lows
    # For each candle after last swing, check closes
    closes = df["close"].astype(float).values if not df.empty else []
    close_times = df["close_time"].values if not df.empty else []
    opens = df["open_time"].values if not df.empty else []
    # need mapping from swing to level
    # Track latest unbroken high and low
    latest_high = highs[-1] if highs else None
    latest_low = lows[-1] if lows else None
    # We'll iterate candles
    n = len(df)
    current_bias = "UNDEFINED"
    # simple: determine current bias by last swing trend: if last swing is high higher than previous high -> BULLISH
    if len(highs)>=2 and len(lows)>=2:
        if highs[-1].price > highs[-2].price and lows[-1].price > lows[-2].price:
            current_bias = "BULLISH"
        elif highs[-1].price < highs[-2].price and lows[-1].price < lows[-2].price:
            current_bias = "BEARISH"
        else:
            current_bias = "UNDEFINED"
    else:
        current_bias = "UNDEFINED"

    # For BOS/CHOCH, we need to walk candles and check breaks
    # Use latest unbroken swing levels
    unbroken_high = latest_high
    unbroken_low = latest_low
    # Keep list of unbroken (not yet broken)
    unbroken_highs = highs.copy()
    unbroken_lows = lows.copy()

    for i in range(n):
        close = float(closes[i])
        bar_time = pd.to_datetime(close_times[i]).to_pydatetime()
        atr = float(atr_series.iloc[i]) if atr_series is not None and i < len(atr_series) and not pd.isna(atr_series.iloc[i]) else 1.0
        buffer = bos_buffer_atr * atr
        # check upside break
        if unbroken_high and close > float(unbroken_high.price) + buffer:
            # break
            if current_bias in ("BULLISH","UNDEFINED"):
                typ = "BOS"
                new_bias = "BULLISH"
            else:
                typ = "CHOCH"
                new_bias = "BULLISH"
                # This is CHOCH_BULL
                if current_bias == "BEARISH":
                    typ = "CHOCH_BULL"
            ev = StructureEvent(event_id=f"bos-{i}-{unbroken_high.swing_id}", type=typ, direction="BULL", broken_swing_id=unbroken_high.swing_id, broken_level=unbroken_high.price, break_bar_time=bar_time, break_price=Decimal(str(close)), bias_before=current_bias, bias_after=new_bias)
            events.append(ev)
            broken_ids.add(unbroken_high.swing_id)
            # remove broken and set next
            unbroken_highs = [h for h in unbroken_highs if h.swing_id != unbroken_high.swing_id]
            unbroken_high = unbroken_highs[-1] if unbroken_highs else None
            current_bias = new_bias
            continue
        # downside break
        if unbroken_low and close < float(unbroken_low.price) - buffer:
            if current_bias in ("BEARISH","UNDEFINED"):
                typ = "BOS"
                new_bias = "BEARISH"
            else:
                typ = "CHOCH"
                new_bias = "BEARISH"
                if current_bias == "BULLISH":
                    typ = "CHOCH_BEAR"
            ev = StructureEvent(event_id=f"bos-{i}-{unbroken_low.swing_id}", type=typ, direction="BEAR", broken_swing_id=unbroken_low.swing_id, broken_level=unbroken_low.price, break_bar_time=bar_time, break_price=Decimal(str(close)), bias_before=current_bias, bias_after=new_bias)
            events.append(ev)
            broken_ids.add(unbroken_low.swing_id)
            unbroken_lows = [l for l in unbroken_lows if l.swing_id != unbroken_low.swing_id]
            unbroken_low = unbroken_lows[-1] if unbroken_lows else None
            current_bias = new_bias

    # mark broken
    for s in swings:
        if s.swing_id in broken_ids:
            s.status = "BROKEN"
    return events, current_bias
