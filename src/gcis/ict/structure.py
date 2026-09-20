"""
ICT-02 Structure BOS/CHOCH — causal, deterministic, no-repaint
Config (ict.structure):
  break_on close
  min_break_atr 0.10

Definition:
  Bias UNDEFINED until >=2 HIGHs and >=2 LOWs confirmed.
  Initial bias from last swings: if last high > prev high and last low > prev low → BULLISH
                              elif last high < prev high and last low < prev low → BEARISH else UNDEFINED.
  Levels: latest confirmed unbroken swing HIGH (most recent CONFIRMED not BROKEN)
          and swing LOW similarly. Maintained as stacks (sorted by bar_time).
  Break: close exceeds level by buffer = min_break_atr * ATR[bar] (close-based, causal per bar).
         For upside: close > swing_high.price + buffer
         For downside: close < swing_low.price - buffer
         A break consumes the broken swing (marks BROKEN) and updates bias:
           if bias prior BULLISH/UNDEFINED and upside break → BOS BULL else CHOCH_BULL
           if bias prior BEARISH/UNDEFINED and downside break → BOS BEAR else CHOCH_BEAR
         For strict BOS vs CHOCH, CHOCH is when break flips bias.
         We emit type BOS or CHOCH_BULL/CHOCH_BEAR accordingly.
  No repaint: once structure event confirmed at close, never removed by future.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple
from decimal import Decimal
from datetime import datetime
import pandas as pd
from gcis.ict.swings import Swing

@dataclass
class StructureEvent:
    event_id: str
    type: str  # BOS, CHOCH_BULL, CHOCH_BEAR (CHOCH generic also possible)
    direction: str  # BULL BEAR
    broken_swing_id: str
    broken_level: Decimal
    break_bar_time: datetime
    break_price: Decimal
    bias_before: str
    bias_after: str

def detect_structure(
    swings: List[Swing],
    df: pd.DataFrame,
    bos_buffer_atr: float = 0.10,
    atr_series=None,
) -> Tuple[List[StructureEvent], str]:
    if not swings:
        return [], "UNDEFINED"
    swings_sorted = sorted(swings, key=lambda s: s.confirmation_at)
    highs = [s for s in swings_sorted if s.type == "HIGH" and s.status == "CONFIRMED"]
    lows = [s for s in swings_sorted if s.type == "LOW" and s.status == "CONFIRMED"]
    if len(highs) < 2 or len(lows) < 2:
        return [], "UNDEFINED"
    closes = df["close"].astype(float).values if not df.empty else []
    close_times = df["close_time"].values if not df.empty else []
    n = len(df)
    # initial bias from last swings (deterministic)
    current_bias = "UNDEFINED"
    if highs[-1].price > highs[-2].price and lows[-1].price > lows[-2].price:
        current_bias = "BULLISH"
    elif highs[-1].price < highs[-2].price and lows[-1].price < lows[-2].price:
        current_bias = "BEARISH"
    else:
        current_bias = "UNDEFINED"

    # stacks of unbroken levels — most recent last
    unbroken_highs = highs.copy()
    unbroken_lows = lows.copy()
    # keep pointer to latest unbroken (last in list)
    events: List[StructureEvent] = []
    broken_ids = set()

    def _to_utc_ts(dt):
        try:
            return pd.to_datetime(dt, utc=True)
        except:
            return pd.to_datetime(str(dt), utc=True)
    for i in range(n):
        close = float(closes[i])
        bar_time_raw = close_times[i]
        bar_time = _to_utc_ts(bar_time_raw)
        atr = float(atr_series.iloc[i]) if atr_series is not None and i < len(atr_series) and not pd.isna(atr_series.iloc[i]) else 1.0
        buffer = bos_buffer_atr * atr

        # only swings whose confirmation_at <= bar close are eligible to be broken (causal)
        # we sort already, but ensure swing bar_time <= bar close time? swings confirmed after p+R, so a swing whose pivot is recent but not yet confirmed should not be breakable.
        # Filter unbroken to only those with confirmation_at <= bar_time
        # Build eligible latest — use UTC-aware compare to avoid naive/aware error
        eligible_highs = [h for h in unbroken_highs if _to_utc_ts(h.confirmation_at) <= bar_time]
        eligible_lows = [l for l in unbroken_lows if _to_utc_ts(l.confirmation_at) <= bar_time]
        latest_high = eligible_highs[-1] if eligible_highs else None
        latest_low = eligible_lows[-1] if eligible_lows else None

        handled = False
        # convert bar_time Timestamp to aware datetime for event
        bar_time_dt = bar_time.to_pydatetime() if hasattr(bar_time, "to_pydatetime") else bar_time
        if latest_high and close > float(latest_high.price) + buffer:
            # upside break
            bias_before = current_bias
            if current_bias in ("BULLISH", "UNDEFINED"):
                typ = "BOS"
                new_bias = "BULLISH"
            else:  # BEARISH -> flip
                typ = "CHOCH_BULL"
                new_bias = "BULLISH"
            ev = StructureEvent(
                event_id=f"bos-{i}-{latest_high.swing_id}",
                type=typ,
                direction="BULL",
                broken_swing_id=latest_high.swing_id,
                broken_level=latest_high.price,
                break_bar_time=bar_time_dt,
                break_price=Decimal(str(close)),
                bias_before=bias_before,
                bias_after=new_bias,
            )
            events.append(ev)
            broken_ids.add(latest_high.swing_id)
            unbroken_highs = [h for h in unbroken_highs if h.swing_id != latest_high.swing_id]
            current_bias = new_bias
            handled = True
            # do not also check low break same bar (prioritise high break then next bar will handle low)
        if not handled and latest_low and close < float(latest_low.price) - buffer:
            bias_before = current_bias
            if current_bias in ("BEARISH", "UNDEFINED"):
                typ = "BOS"
                new_bias = "BEARISH"
            else:
                typ = "CHOCH_BEAR"
                new_bias = "BEARISH"
            ev = StructureEvent(
                event_id=f"bos-{i}-{latest_low.swing_id}",
                type=typ,
                direction="BEAR",
                broken_swing_id=latest_low.swing_id,
                broken_level=latest_low.price,
                break_bar_time=bar_time_dt,
                break_price=Decimal(str(close)),
                bias_before=bias_before,
                bias_after=new_bias,
            )
            events.append(ev)
            broken_ids.add(latest_low.swing_id)
            unbroken_lows = [l for l in unbroken_lows if l.swing_id != latest_low.swing_id]
            current_bias = new_bias

    for s in swings:
        if s.swing_id in broken_ids:
            s.status = "BROKEN"
    return events, current_bias
