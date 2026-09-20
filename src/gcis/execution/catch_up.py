"""
EXE-06 Downtime catch-up — replay missed candles from archive/parquet
Idempotent via unique open_time.
For test we use in-memory registry of seen open_times per venue:symbol:tf
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import List

_seen = set()

def catch_up_missing(missed_candles: List[dict], venue: str, symbol: str, timeframe: str) -> int:
    """
    Ingests missed candles, returns count of newly ingested (dedup by open_time).
    For test, we track in global _seen set keyed by (venue,symbol,timeframe,open_time iso)
    """
    count = 0
    for c in missed_candles:
        ot = c.get("open_time")
        if isinstance(ot, str):
            try:
                ot = datetime.fromisoformat(ot.replace("Z","+00:00"))
            except:
                continue
        if ot is None:
            continue
        if ot.tzinfo is None:
            ot = ot.replace(tzinfo=timezone.utc)
        key = (venue, symbol, timeframe, ot.isoformat())
        if key not in _seen:
            _seen.add(key)
            count += 1
        # else duplicate idempotent -> 0
    return count

def reset_catch_up_state():
    global _seen
    _seen = set()
