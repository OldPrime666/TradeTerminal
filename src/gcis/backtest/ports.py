"""Backtest ports — domain interfaces, no sqlalchemy import, satisfies Domain must not import sqlalchemy via inversion."""

from typing import Protocol, List, Any, Optional

class CandleRepository(Protocol):
    def fetch(self, symbols: List[str], timeframe: str, start: Optional[str] = None, end: Optional[str] = None, limit: int = 5000) -> List[Any]:
        ...
