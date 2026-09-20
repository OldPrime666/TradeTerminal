from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List
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

def detect_order_blocks(df: pd.DataFrame, symbol: str, timeframe: str, structure_events, cfg: dict) -> List[OrderBlock]:
    """
    Bullish OB = last bearish candle (or cluster <= max_cluster) immediately before bullish displacement that produces BOS/CHOCH within lookahead_bars
    Simplified: find BOS events, look back for last bearish candle before displacement.
    """
    if df is None or df.empty or not structure_events:
        return []
    obs=[]
    max_cluster = 3  # default
    # map break times to event
    for ev in structure_events:
        if ev.direction != "BULL":
            continue  # demo only bullish for Spot long
        # find bar index of break
        # locate where close_time == break_bar_time
        idx = None
        for i, ct in enumerate(df["close_time"]):
            if pd.to_datetime(ct).to_pydatetime() == ev.break_bar_time:
                idx = i
                break
        if idx is None:
            continue
        # look back up to 5 bars for last bearish candle
        lookback = 5
        start = max(0, idx - lookback)
        # find bullish displacement at idx? we approximate: check that break candle is bullish displacement (body/range)
        # Find last bearish candle before idx
        for j in range(idx-1, start-1, -1):
            open_ = float(df.iloc[j]["open"])
            close = float(df.iloc[j]["close"])
            if close < open_:  # bearish
                # need displacement + BOS requirement already satisfied (ev exists)
                # zone = body by default
                high = float(df.iloc[j]["high"]); low = float(df.iloc[j]["low"])
                # body zone
                zone_high = Decimal(str(max(open_, close)))
                zone_low = Decimal(str(min(open_, close)))
                # if full range optional, use high/low but we use body
                origin_time = pd.to_datetime(df.iloc[j]["open_time"]).to_pydatetime()
                created_at = ev.break_bar_time
                obs.append(OrderBlock(ob_id=f"{symbol}-{timeframe}-obB-{j}-{idx}", symbol=symbol, timeframe=timeframe, direction="BULL", zone_high=zone_high, zone_low=zone_low, origin_time=origin_time, created_at=created_at, structure_break_id=ev.event_id, mitigation_state="FRESH"))
                break
    return obs
