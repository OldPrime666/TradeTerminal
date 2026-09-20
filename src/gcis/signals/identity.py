"""
SIG-04 Identity + dedup ULID, SIG-05 TTL handled in lifecycle but dedup window here.
dedup_window_bars 6 (config signal.dedup_window_bars) — same symbol/direction/timeframe within 6 bars => duplicate.
ULID for signal_id monotonic sort.
"""
import ulid
from datetime import datetime, timezone, timedelta
from typing import List, Dict

def generate_signal_id() -> str:
    """
    Generates ULID string (Crockford base32, time-ordered).
    """
    return str(ulid.ULID())

def is_duplicate(new_signal: Dict, existing_signals: List[Dict], dedup_window_bars: int, timeframe: str) -> bool:
    """
    Checks if new_signal duplicates an existing signal within dedup window.
    new_signal dict must contain symbol, direction, primary_timeframe, created_at
    existing_signals: list of dicts with same keys + created_at
    dedup_window: 6 bars
    timeframe: e.g., 5m -> 5 min per bar
    """
    if not existing_signals:
        return False
    tf_min = {"1m":1,"5m":5,"15m":15,"1h":60,"4h":240,"1d":1440}
    mins_per_bar = tf_min.get(timeframe, 15)
    window = timedelta(minutes=mins_per_bar * dedup_window_bars)
    new_time = new_signal.get("created_at")
    if isinstance(new_time, str):
        try:
            new_time = datetime.fromisoformat(new_time.replace("Z","+00:00"))
        except:
            new_time = datetime.now(timezone.utc)
    if new_time.tzinfo is None:
        new_time = new_time.replace(tzinfo=timezone.utc)
    for sig in existing_signals:
        if sig.get("symbol") != new_signal.get("symbol"):
            continue
        if sig.get("direction") != new_signal.get("direction"):
            continue
        if sig.get("primary_timeframe") != new_signal.get("primary_timeframe"):
            continue
        existing_time = sig.get("created_at")
        if isinstance(existing_time, str):
            try:
                existing_time = datetime.fromisoformat(existing_time.replace("Z","+00:00"))
            except:
                continue
        if existing_time.tzinfo is None:
            existing_time = existing_time.replace(tzinfo=timezone.utc)
        delta = abs((new_time - existing_time).total_seconds())
        if delta <= window.total_seconds():
            return True
    return False

def normalize_signal_dict(strategy_result, view, symbol: str, timeframe: str, created_at: datetime, signal_id: str = None) -> Dict:
    """
    Builds dict for dedup and persistence, includes required contract fields.
    """
    return {
        "signal_id": signal_id or generate_signal_id(),
        "symbol": symbol,
        "direction": getattr(strategy_result, "direction", None),
        "primary_timeframe": timeframe,
        "created_at": created_at,
        "setup_score": getattr(strategy_result, "setup_score", 0),
        "strategy": getattr(strategy_result, "strategy_name", "ICT-A"),
    }
