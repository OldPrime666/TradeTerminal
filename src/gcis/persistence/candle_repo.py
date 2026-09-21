"""Persistence adapter for backtest candle fetch — implements backtest.ports.CandleRepository.

Only place where backtest data fetching touches sqlalchemy.
Domain (gcis.backtest) must not import sqlalchemy directly.
"""
from datetime import datetime, timezone
from typing import List, Optional, Any

class SqlAlchemyCandleRepository:
    """Adapter that implements CandleRepository using SQLAlchemy."""

    def fetch(self, symbols: List[str], timeframe: str, start: Optional[str] = None, end: Optional[str] = None, limit: int = 5000) -> List[Any]:
        # Lazy imports to keep module load light
        from gcis.persistence.db import get_session
        from gcis.persistence.models import Candle

        db = get_session()
        try:
            q = db.query(Candle).filter(Candle.symbol.in_(symbols), Candle.timeframe == timeframe)
            if start:
                try:
                    s = datetime.fromisoformat(start).replace(tzinfo=timezone.utc) if "T" in start else datetime.fromisoformat(start + "T00:00:00").replace(tzinfo=timezone.utc)
                    q = q.filter(Candle.open_time >= s)
                except Exception:
                    pass
            if end:
                try:
                    e = datetime.fromisoformat(end).replace(tzinfo=timezone.utc) if "T" in end else datetime.fromisoformat(end + "T23:59:59").replace(tzinfo=timezone.utc)
                    q = q.filter(Candle.open_time <= e)
                except Exception:
                    pass
            rows = q.order_by(Candle.open_time).limit(limit).all()
            return rows
        finally:
            db.close()
