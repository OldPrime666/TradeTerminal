"""
ARC-20 incremental engine — only affected contracts recomputed.
Keeps cache of MarketView per symbol/timeframe and updates only on new closed candle.
Deterministic.
"""
from typing import Dict, Any, Set, List
import pandas as pd
from datetime import datetime, timezone
from gcis.market.view import MarketView

class IncrementalEngine:
    """
    Caches last processed as_of per symbol/timeframe.
    On bundle, computes which symbols have new closed candle (affected) and recomputes view only for them.
    For unaffected, returns cached result.
    """
    def __init__(self):
        self.cache: Dict[str, Any] = {}  # key symbol:tf -> (as_of, result)
        self.processed_count = 0
        self.skipped_count = 0

    def is_affected(self, symbol: str, timeframe: str, latest_close_time: datetime, last_as_of: datetime | None) -> bool:
        if last_as_of is None:
            return True
        # affected if latest close > last processed as_of
        if latest_close_time.tzinfo is None:
            latest_close_time = latest_close_time.replace(tzinfo=timezone.utc)
        if last_as_of.tzinfo is None:
            last_as_of = last_as_of.replace(tzinfo=timezone.utc)
        return latest_close_time > last_as_of

    def update(self, symbol: str, timeframe: str, candles_df: pd.DataFrame, as_of: datetime, compute_fn):
        """
        candles_df: full df up to as_of for symbol/timeframe
        compute_fn: callable returning result for this symbol (e.g., strategy eval)
        Returns result (cached if not affected, recomputed if affected)
        """
        key = f"{symbol}:{timeframe}"
        last = self.cache.get(key)
        last_as_of = last[0] if last else None
        latest_close = candles_df["close_time"].iloc[-1] if not candles_df.empty else as_of
        if isinstance(latest_close, str):
            latest_close = pd.Timestamp(latest_close)
        if isinstance(latest_close, pd.Timestamp) and latest_close.tz is None:
            latest_close = latest_close.tz_localize("UTC")
        elif hasattr(latest_close, "tzinfo") and latest_close.tzinfo is None:
            latest_close = latest_close.replace(tzinfo=timezone.utc)
        affected = self.is_affected(symbol, timeframe, latest_close, last_as_of)
        if affected or last is None:
            result = compute_fn()
            self.cache[key] = (as_of, result)
            self.processed_count +=1
            return {"result": result, "affected": True, "cached": False, "as_of": as_of}
        else:
            self.skipped_count +=1
            return {"result": last[1], "affected": False, "cached": True, "as_of": last_as_of}

    def bundle_update(self, symbols: List[str], timeframe: str, candles_dict: Dict[str, pd.DataFrame], as_of: datetime, compute_fn_for_symbol):
        """
        Batch update for prioritised symbols bundle.
        candles_dict: symbol -> df
        compute_fn_for_symbol: fn(symbol) -> result
        Returns dict symbol -> update result, plus stats.
        """
        results = {}
        affected_set: Set[str] = set()
        for sym in symbols:
            df = candles_dict.get(sym, pd.DataFrame())
            if df.empty:
                results[sym] = {"result": None, "affected": False, "cached": False, "status": "NO_DATA"}
                continue
            res = self.update(sym, timeframe, df, as_of, lambda s=sym: compute_fn_for_symbol(s))
            results[sym] = res
            if res["affected"]:
                affected_set.add(sym)
        stats = {
            "total": len(symbols),
            "affected": len(affected_set),
            "skipped": len(symbols) - len(affected_set),
            "processed_count": self.processed_count,
            "skipped_count": self.skipped_count,
            "affected_set": list(affected_set)[:5],
            "note": "Incremental: only affected contracts recomputed"
        }
        return {"results": results, "stats": stats}

    def invalidate(self, symbol: str | None = None):
        if symbol is None:
            self.cache.clear()
        else:
            keys = [k for k in self.cache if k.startswith(f"{symbol}:")]
            for k in keys:
                del self.cache[k]
