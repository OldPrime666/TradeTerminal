"""
ICT-05 Order Block — causal, requires BOS, displacement within 3, max_age 300
Config:
  displacement_within_bars 3
  require_bos true
  max_age_bars 300
  use_body_zone true
  (also uses displacement cfg and structure min_break_atr)

Definition:
  Bullish OB = last bearish candle (close < open) that is within displacement_within_bars
               before a bullish displacement that leads to BOS/CHOCH_BULL within same window.
               Zone by default is body [min(open,close), max(open,close)] if use_body_zone else [low, high].
               Bearish opposite: last bullish candle before bearish displacement+ BOS_BEAR.
               Must have displacement (body/range >=0.60) on the impulse bar.
               Must have structure event BOS/CHOCH linked (require_bos).
               Created at break time (confirmation). Mitigation separate.

  Causality: only closed bars; OB origin precedes break; break → confirmation.
  No repaint: once OB created at break, persisted.

  max_age_bars used by mitigation to invalidate OLD OBs >300 bars without retest.

Spec relative units ICT-11.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import pandas as pd

@dataclass
class OrderBlock:
    ob_id: str
    symbol: str
    timeframe: str
    direction: str  # BULL BEAR
    zone_high: Decimal
    zone_low: Decimal
    origin_time: datetime
    created_at: datetime
    structure_break_id: str
    mitigation_state: str  # FRESH TOUCHED MITIGATED INVALIDATED
    origin_index: int
    break_index: int

def detect_order_blocks(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    structure_events,
    cfg: Optional[dict] = None,
    atr_series=None,
    displacement_indices=None,
) -> List[OrderBlock]:
    """
    Detect OBs linked to structure events.
    cfg may be dict of order_block params or legacy positionally passed as {}
    For backward compat: if cfg is dict and contains displacement params, ignore.
    If caller passes cfg as 5th positional (old) it is dict.
    We also accept displacement_indices as separate arg.
    To keep compatibility with old call detect_order_blocks(df, symbol, tf, events, {}),
    we interpret cfg accordingly.
    """
    if df is None or df.empty or not structure_events:
        return []
    # handle legacy signature where 5th arg is cfg dict but caller expects displacement_indices=None
    # Our signature now: (df, symbol, tf, events, cfg=None, atr_series=None, displacement_indices=None)
    # Old call: detect_order_blocks(df, symbol, tf, struct_setup, {})
    # That will set cfg={} correctly.
    if cfg is None:
        cfg = {}
    # defaults matching config/default.yaml
    defaults = {
        "displacement_within_bars": 3,
        "require_bos": True,
        "max_age_bars": 300,
        "use_body_zone": True,
    }
    for k, v in defaults.items():
        cfg.setdefault(k, v)

    displacement_within = cfg.get("displacement_within_bars", 3)
    require_bos = cfg.get("require_bos", True)
    use_body_zone = cfg.get("use_body_zone", True)
    # max_age is for later invalidation, not for detection
    obs: List[OrderBlock] = []
    # build map from break_bar_time to index
    close_times = list(df["close_time"])
    # for fast lookup, create dict time->index
    time_to_idx = {}
    for idx, ct in enumerate(close_times):
        try:
            t = pd.to_datetime(ct).to_pydatetime()
            time_to_idx[t] = idx
        except:
            pass

    for ev in structure_events:
        if require_bos and ev.type not in ("BOS", "CHOCH_BULL", "CHOCH_BEAR"):
            # require BOS/CHOCH; if require_bos true, allow both; but if event is something else skip
            continue
        # only bullish BOS -> bullish OB, bearish BOS -> bearish OB
        if ev.direction == "BULL":
            ob_dir = "BULL"
            # bearish candle is origin
            want_bearish_origin = True
        elif ev.direction == "BEAR":
            ob_dir = "BEAR"
            want_bearish_origin = False
        else:
            continue
        break_idx = time_to_idx.get(ev.break_bar_time, None)
        if break_idx is None:
            # try approximate: find nearest close_time <= break_bar_time? For deterministic we require exact match
            continue
        # Check displacement within window before break
        # Find displacement indices within [break_idx - displacement_within, break_idx]
        has_displacement_window = False
        disp_in_window = []
        if displacement_indices is not None:
            for k in range(max(0, break_idx - displacement_within), break_idx + 1):
                if k in displacement_indices:
                    has_displacement_window = True
                    disp_in_window.append(k)
        else:
            # if not provided, we cannot enforce but allow (legacy)
            has_displacement_window = True

        if not has_displacement_window:
            continue

        # Find last opposite candle before break within lookback 5? spec says displacement_within_bars,
        # but origin is the last opposite candle immediately before impulse.
        # We search backwards from break_idx-1 down to break_idx - 5 (or within window)
        lookback = 5  # practical window to find origin
        start = max(0, break_idx - lookback)
        # If we have disp indices, we should look for origin just before the displacement impulse
        # The impulse is the displacement bar; find the most recent displacement in window, then origin before it
        impulse_idx = None
        if displacement_indices is not None and disp_in_window:
            # choose the latest displacement in window that is <= break_idx
            impulse_idx = max(d for d in disp_in_window if d <= break_idx)
        else:
            impulse_idx = break_idx  # fallback: assume break candle is impulse

        # origin search: last opposite candle before impulse
        origin_idx = None
        for j in range(impulse_idx - 1, start - 1, -1):
            open_ = float(df.iloc[j]["open"])
            close = float(df.iloc[j]["close"])
            is_bearish = close < open_
            if want_bearish_origin and is_bearish:
                origin_idx = j
                break
            if not want_bearish_origin and not is_bearish and close != open_:
                # bullish origin for bearish OB (close > open)
                if close > open_:
                    origin_idx = j
                    break
        if origin_idx is None:
            continue
        # build zone
        open_o = float(df.iloc[origin_idx]["open"])
        close_o = float(df.iloc[origin_idx]["close"])
        high_o = float(df.iloc[origin_idx]["high"])
        low_o = float(df.iloc[origin_idx]["low"])
        if use_body_zone:
            zone_high = Decimal(str(max(open_o, close_o)))
            zone_low = Decimal(str(min(open_o, close_o)))
        else:
            zone_high = Decimal(str(high_o))
            zone_low = Decimal(str(low_o))
        origin_time = pd.to_datetime(df.iloc[origin_idx]["open_time"]).to_pydatetime()
        created_at = ev.break_bar_time
        obs.append(
            OrderBlock(
                ob_id=f"{symbol}-{timeframe}-ob{ob_dir[0]}-{origin_idx}-{break_idx}",
                symbol=symbol,
                timeframe=timeframe,
                direction=ob_dir,
                zone_high=zone_high,
                zone_low=zone_low,
                origin_time=origin_time,
                created_at=created_at,
                structure_break_id=ev.event_id,
                mitigation_state="FRESH",
                origin_index=origin_idx,
                break_index=break_idx,
            )
        )
    return obs
