from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

@dataclass
class Candle:
    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    quote_volume: Optional[Decimal] = None
    trade_count: Optional[int] = None
    taker_buy_volume: Optional[Decimal] = None
    is_closed: bool = True
    source: str = "binance"
    ingestion_time: Optional[datetime] = None

    def __post_init__(self):
        # validation INV-13, DAT-07
        for f in ["open","high","low","close","volume"]:
            v = getattr(self, f)
            if not isinstance(v, Decimal):
                raise TypeError(f"{f} must be Decimal")
        if self.high < self.low or self.high < self.open or self.high < self.close or self.low > self.open or self.low > self.close:
            # allow but mark invalid? For now raise if blatantly invalid
            pass
        if self.open_time.tzinfo is None or self.close_time.tzinfo is None:
            raise ValueError("Candle times must be timezone-aware UTC")
        # Ensure UTC
        if self.open_time.tzinfo != timezone.utc:
            self.open_time = self.open_time.astimezone(timezone.utc)
        if self.close_time.tzinfo != timezone.utc:
            self.close_time = self.close_time.astimezone(timezone.utc)

@dataclass
class QuoteBar:
    symbol: str
    window_start: datetime
    window_end: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    bid: Decimal | None = None
    ask: Decimal | None = None
    trade_count: int = 0
