from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from decimal import Decimal
import pandas as pd

@dataclass
class FormingCandle:
    symbol: str
    timeframe: str
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

@dataclass
class MarketView:
    """
    Point-in-time view as_of — only data with available_at <= as_of is exposed.
    INV-04: no look-ahead.
    """
    as_of: datetime
    candles: Dict[str, Dict[str, pd.DataFrame]] = field(default_factory=dict)  # symbol -> timeframe -> df
    quotes: Dict[str, dict] = field(default_factory=dict)
    features: Dict[str, dict] = field(default_factory=dict)
    regimes: Dict[str, dict] = field(default_factory=dict)
    ict_state: Dict[str, dict] = field(default_factory=dict)
    forming_candles: Dict[str, Dict[str, FormingCandle]] = field(default_factory=dict)

    def get_closed_candles(self, symbol: str, timeframe: str) -> pd.DataFrame:
        dfs = self.candles.get(symbol, {}).get(timeframe)
        if dfs is None or dfs.empty:
            return pd.DataFrame()
        # filter by available_at <= as_of ; available_at = close_time + processing lag (assume 0 for closed)
        # For closed candles, close_time <= as_of
        filtered = dfs[dfs["close_time"] <= self.as_of]
        return filtered

    def get_forming_candle(self, symbol: str, timeframe: str) -> Optional[FormingCandle]:
        return self.forming_candles.get(symbol, {}).get(timeframe)

    def get_available_symbols(self):
        return list(self.candles.keys())

    def is_data_fresh(self, symbol: str, max_age_s: int = 5) -> bool:
        q = self.quotes.get(symbol)
        if not q or "updated_at" not in q:
            return False
        age = (self.as_of - q["updated_at"]).total_seconds()
        return age <= max_age_s

    def quality_state(self, symbol: str, quote_stale_after_s=5, quote_disconnected_after_s=30):
        q = self.quotes.get(symbol)
        if not q or "updated_at" not in q:
            return "NO DATA"
        age = (self.as_of - q["updated_at"]).total_seconds()
        if age <= quote_stale_after_s:
            return "HEALTHY"
        elif age <= quote_disconnected_after_s:
            return "DEGRADED"
        else:
            return "DISCONNECTED"
