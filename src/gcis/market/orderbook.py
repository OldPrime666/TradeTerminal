"""
DOM-01 orderbook engine P3 stub (light for P16)
Provides OrderBook snapshot handling, spread, freshness, imbalance proxy.
For P16 we provide deterministic stub that tracks bids/asks, computes mid/spread, flags stale.
Full DOM with persistence will be P17+.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from decimal import Decimal

class OrderBook:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bids: List[List[Decimal]] = []  # [price, qty]
        self.asks: List[List[Decimal]] = []
        self.updated_at: datetime | None = None
        self.seq: int = 0

    def apply_snapshot(self, bids: List[List[float]], asks: List[List[float]], seq: int | None =None, ts: datetime | None =None):
        self.bids = [[Decimal(str(p)), Decimal(str(q))] for p,q in bids]
        self.asks = [[Decimal(str(p)), Decimal(str(q))] for p,q in asks]
        # sort bids descending asks ascending
        self.bids.sort(key=lambda x: x[0], reverse=True)
        self.asks.sort(key=lambda x: x[0])
        self.updated_at = ts or datetime.now(timezone.utc)
        if seq is not None:
            self.seq = seq
        else:
            self.seq +=1

    def apply_update(self, bids: List[List[float]], asks: List[List[float]], seq: int | None =None, ts: datetime | None =None):
        # For stub, just replace snapshot (delta handling deferred)
        self.apply_snapshot(bids, asks, seq, ts)

    def best_bid(self) -> Optional[Decimal]:
        return self.bids[0][0] if self.bids else None

    def best_ask(self) -> Optional[Decimal]:
        return self.asks[0][0] if self.asks else None

    def mid_price(self) -> Optional[Decimal]:
        b = self.best_bid()
        a = self.best_ask()
        if b is not None and a is not None:
            return (b + a) / 2
        return None

    def spread_bps(self) -> Optional[float]:
        b = self.best_bid()
        a = self.best_ask()
        mid = self.mid_price()
        if b is not None and a is not None and mid and mid !=0:
            return float((a - b) / mid * 10000)
        return None

    def imbalance(self) -> Optional[float]:
        """Bid volume vs ask volume at top 5 levels."""
        if not self.bids or not self.asks:
            return None
        bid_vol = sum(float(q) for _,q in self.bids[:5])
        ask_vol = sum(float(q) for _,q in self.asks[:5])
        total = bid_vol + ask_vol
        if total==0:
            return None
        return (bid_vol - ask_vol)/ total  # -1 to 1

    def freshness_status(self, now: datetime | None =None, stale_after_s: int =5, disconnected_after_s: int =30) -> str:
        if self.updated_at is None:
            return "NO_DATA"
        if now is None:
            now = datetime.now(timezone.utc)
        if self.updated_at.tzinfo is None:
            self.updated_at = self.updated_at.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        age = (now - self.updated_at).total_seconds()
        if age > disconnected_after_s:
            return "DISCONNECTED"
        if age > stale_after_s:
            return "STALE"
        return "HEALTHY"

    def to_snapshot(self) -> Dict[str,Any]:
        return {
            "symbol": self.symbol,
            "bids": [[float(p), float(q)] for p,q in self.bids[:5]],
            "asks": [[float(p), float(q)] for p,q in self.asks[:5]],
            "mid": float(self.mid_price()) if self.mid_price() else None,
            "spread_bps": round(self.spread_bps(),2) if self.spread_bps() else None,
            "imbalance": round(self.imbalance(),3) if self.imbalance() is not None else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "freshness": self.freshness_status(),
            "seq": self.seq,
        }

# Global registry stub
_books: Dict[str, OrderBook] = {}

def get_book(symbol: str) -> OrderBook:
    if symbol not in _books:
        _books[symbol] = OrderBook(symbol)
    return _books[symbol]

def clear_books():
    _books.clear()
