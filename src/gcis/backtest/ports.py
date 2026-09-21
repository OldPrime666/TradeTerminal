"""Backtest domain ports — abstractions for candle data.

Backtest domain must not import sqlalchemy or persistence models directly.
Persistence adapter implements this protocol.
"""
from typing import Protocol, List, Any, Optional

class CandleRepository(Protocol):
    """Abstract candle fetch. Implemented in persistence layer."""

    def fetch(self, symbols: List[str], timeframe: str, start: Optional[str] = None, end: Optional[str] = None, limit: int = 5000) -> List[Any]:
        """Return list of candle rows (objects with attributes open_time, close_time, open, high, low, close, volume)."""
        ...
