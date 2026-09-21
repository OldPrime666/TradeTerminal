"""
Fake exchange harness §43 — offline deterministic harness for transport / analyzer tests.

Provides free-only adapters that never hit network (INV-14/SEC-09), return
recorded fixtures or synthetic deterministic data, and emit WS payloads locally.

Venues covered (same chain as runtime): binance_um, binance_cm, bybit_linear,
okx_swap, hyperliquid — each has a Fake adapter with:
  - fetch_contracts() from fixtures/real/* (CODE_VERIFIED offline)
  - ping() -> True, get_time() -> now µs
  - klines() synthetic deterministic 1m/5m/15m candles
  - bookTicker payload generator for WS

Also: FakeWSHarness for transport manager offline tests without network.
"""
from __future__ import annotations

import json
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Any
from decimal import Decimal

from .base import BaseVenueAdapter

# ---- helpers ----

def _synthetic_klines(symbol: str, interval: str, limit: int = 100, start_ms: int | None = None) -> List[List[Any]]:
    """
    Deterministic synthetic futures klines.
    Returns Binance-style: [openTime, open, high, low, close, volume, closeTime, quoteVolume, trades, tbBase, tbQuote, ignore]
    Deterministic per (symbol, interval, start_ms) — no random.
    """
    # interval to ms
    tf_ms = {"1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}.get(interval, 60_000)
    if start_ms is None:
        # start ~ limit bars ago from now, aligned to tf
        now_ms = int(time.time() * 1000) // tf_ms * tf_ms
        start_ms = now_ms - limit * tf_ms
    # seed per symbol deterministic
    seed = int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16) % 10000
    base_price = 100.0 + (seed % 500) + (hash(symbol) % 100) * 0.1  # deterministic float ~100-600
    # cheap LCG for per-bar delta (deterministic, not random module)
    price = base_price
    out: List[List[Any]] = []
    for i in range(limit):
        open_ms = start_ms + i * tf_ms
        close_ms = open_ms + tf_ms - 1
        # deterministic delta via hash of (symbol, i)
        h = int(hashlib.md5(f"{symbol}:{interval}:{i}".encode()).hexdigest()[:8], 16)
        # delta in range -0.5%..+0.5%
        delta_pct = ((h % 1000) - 500) / 100_000  # -0.005 .. +0.005
        open_p = round(price, 2)
        close_p = round(price * (1 + delta_pct), 2)
        high_p = round(max(open_p, close_p) * (1 + (h % 50) / 100_000), 2)
        low_p = round(min(open_p, close_p) * (1 - (h % 50) / 100_000), 2)
        # ensure high>=low, high>=close/open
        if high_p < max(open_p, close_p):
            high_p = max(open_p, close_p)
        if low_p > min(open_p, close_p):
            low_p = min(open_p, close_p)
        vol = round(10 + (h % 500) + (i % 10), 3)
        quote_vol = round(vol * close_p, 2)
        trades = 100 + (h % 200)
        # update price for next bar
        price = close_p if close_p > 0 else price
        row = [
            open_ms,
            f"{open_p:.2f}",
            f"{high_p:.2f}",
            f"{low_p:.2f}",
            f"{close_p:.2f}",
            f"{vol:.3f}",
            close_ms,
            f"{quote_vol:.2f}",
            trades,
            f"{vol * 0.6:.3f}",
            f"{quote_vol * 0.6:.2f}",
            "0",
        ]
        out.append(row)
    return out


def _bookticker_payload(symbol: str, bid: float | None = None, ask: float | None = None) -> Dict[str, Any]:
    """Deterministic bookTicker payload for WS harness."""
    if bid is None or ask is None:
        seed = int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16)
        mid = 100.0 + (seed % 500)
        spread = 0.01 + (seed % 10) * 0.001
        bid = round(mid - spread / 2, 2)
        ask = round(mid + spread / 2, 2)
    now_ms = int(time.time() * 1000)
    return {
        "e": "bookTicker",
        "u": now_ms,
        "s": symbol,
        "b": f"{bid:.2f}",
        "B": "10.0",
        "a": f"{ask:.2f}",
        "A": "10.0",
        "E": now_ms,
    }


def _kline_ws_payload(symbol: str, interval: str = "1m", price: float = 100.0) -> Dict[str, Any]:
    """Single kline WS closed payload."""
    now_ms = int(time.time() * 1000) // 60000 * 60000
    close_ms = now_ms + 59999
    return {
        "e": "kline",
        "E": now_ms + 60000,
        "s": symbol,
        "k": {
            "t": now_ms,
            "T": close_ms,
            "s": symbol,
            "i": interval,
            "f": 100,
            "L": 200,
            "o": f"{price:.2f}",
            "c": f"{price + 0.5:.2f}",
            "h": f"{price + 1:.2f}",
            "l": f"{price - 0.5:.2f}",
            "v": "10.0",
            "n": 100,
            "x": True,
            "q": "1000.0",
            "V": "6.0",
            "Q": "600.0",
            "B": "0",
        },
    }


FIXTURE_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "real"
# also support cwd-relative when running from different root
_ALT_FIXTURE_DIR = Path("tests/fixtures/real")


def _load_fixture(name: str) -> Dict[str, Any] | None:
    for d in (FIXTURE_DIR, _ALT_FIXTURE_DIR):
        p = d / name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return None
    return None


# ---- Fake adapters ----

class FakeBinanceUMAdapter(BaseVenueAdapter):
    venue_id = "binance_um"
    rest_base = "https://fapi.binance.com"
    ws_base = "wss://fstream.binance.com"
    requests_per_min = 2400

    def ping(self) -> bool:
        return True

    def get_time(self) -> int:
        return int(time.time() * 1_000_000)

    def fetch_contracts(self) -> List[Dict[str, Any]]:
        from .binance_um import BinanceUMAdapter
        data = _load_fixture("binance_um_exchangeInfo.json")
        if data is not None:
            return BinanceUMAdapter.parse_exchange_info(data, venue=self.venue_id)
        # fallback synthetic 5
        return [
            {"venue": self.venue_id, "symbol": s, "base": s.replace("USDT", ""), "quote": "USDT", "settle_asset": "USDT", "contract_family": "LINEAR", "contract_type": "PERPETUAL", "status": "TRADING", "tick_size": Decimal("0.01"), "step_size": Decimal("0.001"), "min_notional": Decimal("5"), "margin_asset": "USDT", "asset_class": "CRYPTO", "max_leverage": 125}
            for s in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
        ]

    def klines(self, symbol: str, interval: str, limit: int = 100, startTime: int | None = None, endTime: int | None = None) -> List[List[Any]]:
        # startTime expected ms or µs — normalize to ms
        start_ms = None
        if startTime is not None:
            start_ms = startTime // 1000 if startTime > 1_000_000_000_000_000 else startTime
            if start_ms > 1_000_000_000_000_000:  # still µs?
                start_ms //= 1000
        if limit <= 0:
            limit = 100
        if limit > 1500:
            limit = 1500
        return _synthetic_klines(symbol, interval, limit=limit, start_ms=start_ms)


class FakeBinanceCMAdapter(BaseVenueAdapter):
    venue_id = "binance_cm"
    rest_base = "https://dapi.binance.com"
    ws_base = "wss://dstream.binance.com"
    requests_per_min = 2400

    def ping(self) -> bool:
        return True

    def get_time(self) -> int:
        return int(time.time() * 1_000_000)

    def fetch_contracts(self) -> List[Dict[str, Any]]:
        # No CM fixture yet — return synthetic inverse contracts
        return [
            {"venue": self.venue_id, "symbol": s, "base": s.replace("USD_PERP", "").replace("USD", ""), "quote": "USD", "settle_asset": "BTC", "contract_family": "INVERSE", "contract_type": "PERPETUAL", "status": "TRADING", "tick_size": Decimal("0.10"), "step_size": Decimal("1"), "min_notional": Decimal("5"), "margin_asset": "BTC", "asset_class": "CRYPTO"}
            for s in ["BTCUSD_PERP", "ETHUSD_PERP"]
        ]

    def klines(self, symbol: str, interval: str, limit: int = 100, startTime: int | None = None, endTime: int | None = None) -> List[List[Any]]:
        start_ms = None
        if startTime is not None:
            start_ms = startTime // 1000 if startTime > 1_000_000_000_000_000 else startTime
        return _synthetic_klines(symbol, interval, limit=min(limit, 1500), start_ms=start_ms)


class FakeBybitAdapter(BaseVenueAdapter):
    venue_id = "bybit_linear"
    rest_base = "https://api.bybit.com"
    ws_base = "wss://stream.bybit.com/v5/public/linear"
    requests_per_min = 1200

    def ping(self) -> bool:
        return True

    def get_time(self) -> int:
        return int(time.time() * 1_000_000)

    def fetch_contracts(self) -> List[Dict[str, Any]]:
        from .bybit import BybitAdapter
        data = _load_fixture("bybit_instruments_linear.json")
        if data is not None:
            try:
                return BybitAdapter.parse_instruments_info(data, category="linear")
            except Exception:
                pass
        return [
            {"venue": self.venue_id, "symbol": s, "base": s.replace("USDT", ""), "quote": "USDT", "settle_asset": "USDT", "contract_family": "LINEAR", "contract_type": "PERPETUAL", "status": "TRADING", "tick_size": Decimal("0.10"), "step_size": Decimal("0.001"), "min_notional": Decimal("5"), "margin_asset": "USDT", "asset_class": "CRYPTO"}
            for s in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        ]

    def klines(self, symbol: str, interval: str, limit: int = 100, startTime: int | None = None, endTime: int | None = None) -> List[List[Any]]:
        start_ms = None
        if startTime is not None:
            start_ms = startTime // 1000 if startTime > 1_000_000_000_000_000 else startTime
        return _synthetic_klines(symbol, interval, limit=min(limit, 1000), start_ms=start_ms)


class FakeOKXAdapter(BaseVenueAdapter):
    venue_id = "okx_swap"
    rest_base = "https://www.okx.com"
    ws_base = "wss://ws.okx.com:8443/ws/v5/public"

    def ping(self) -> bool:
        return True

    def get_time(self) -> int:
        return int(time.time() * 1_000_000)

    def fetch_contracts(self) -> List[Dict[str, Any]]:
        from .okx import OKXAdapter
        data = _load_fixture("okx_swap_instruments.json")
        if data is not None:
            try:
                return OKXAdapter.parse_instruments(data, instType="SWAP")
            except Exception:
                pass
        return [
            {"venue": self.venue_id, "symbol": s, "base": s.split("-")[0], "quote": "USDT", "settle_asset": "USDT", "contract_family": "LINEAR", "contract_type": "PERPETUAL", "status": "TRADING", "tick_size": Decimal("0.01"), "step_size": Decimal("0.01"), "min_notional": Decimal("5"), "margin_asset": "USDT", "asset_class": "CRYPTO"}
            for s in ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
        ]

    def klines(self, symbol: str, interval: str, limit: int = 100, startTime: int | None = None, endTime: int | None = None) -> List[List[Any]]:
        # OKX uses bar e.g. 1m -> same
        start_ms = None
        if startTime is not None:
            start_ms = startTime // 1000 if startTime > 1_000_000_000_000_000 else startTime
        return _synthetic_klines(symbol.replace("-", ""), interval, limit=min(limit, 1000), start_ms=start_ms)


class FakeHyperliquidAdapter(BaseVenueAdapter):
    venue_id = "hyperliquid"
    rest_base = "https://api.hyperliquid.xyz"
    ws_base = "wss://api.hyperliquid.xyz/ws"

    def ping(self) -> bool:
        return True

    def get_time(self) -> int:
        return int(time.time() * 1_000_000)

    def fetch_contracts(self) -> List[Dict[str, Any]]:
        from .hyperliquid import HyperliquidAdapter
        data = _load_fixture("hyperliquid_meta.json")
        if data is not None:
            try:
                return HyperliquidAdapter.parse_meta(data)
            except Exception:
                pass
        return [
            {"venue": self.venue_id, "symbol": s, "base": s, "quote": "USDC", "settle_asset": "USDC", "contract_family": "LINEAR", "contract_type": "PERPETUAL", "status": "TRADING", "tick_size": Decimal("0.01"), "step_size": Decimal("0.01"), "min_notional": Decimal("5"), "margin_asset": "USDC", "asset_class": "CRYPTO"}
            for s in ["BTC", "ETH", "SOL", "ARB"]
        ]

    def klines(self, symbol: str, interval: str, limit: int = 100, startTime: int | None = None, endTime: int | None = None) -> List[List[Any]]:
        start_ms = None
        if startTime is not None:
            start_ms = startTime // 1000 if startTime > 1_000_000_000_000_000 else startTime
        return _synthetic_klines(symbol, interval, limit=min(limit, 5000), start_ms=start_ms)


# Venue -> Fake adapter class
FAKE_ADAPTERS: Dict[str, Any] = {
    "binance_um": FakeBinanceUMAdapter,
    "binance_cm": FakeBinanceCMAdapter,
    "bybit_linear": FakeBybitAdapter,
    "bybit_inverse": FakeBybitAdapter,
    "okx_swap": FakeOKXAdapter,
    "hyperliquid": FakeHyperliquidAdapter,
    "gate_linear": FakeBybitAdapter,  # gate fallback uses bybit synthetic
    "bitget_linear": FakeBybitAdapter,
}


def get_fake_adapter(venue_id: str, **kwargs) -> BaseVenueAdapter:
    """Factory for offline harness — never hits network."""
    cls = FAKE_ADAPTERS.get(venue_id, FakeBinanceUMAdapter)
    return cls(**kwargs)


# ---- WS harness ----

class FakeWSHarness:
    """
    Deterministic WS harness for transport manager tests — emits bookTicker + kline
    payloads without network. Use to test handle_kline_message / handle_bookticker.

    Example:
        harness = FakeWSHarness(symbols=["BTCUSDT","ETHUSDT"], venue="binance_um")
        for payload, ts_us in harness.stream(n=10):
            await handle_kline_message(payload, ts_us, venue="binance_um")
    """

    def __init__(self, symbols: List[str] | None = None, venue: str = "binance_um", interval: str = "1m"):
        self.symbols = symbols or ["BTCUSDT", "ETHUSDT"]
        self.venue = venue
        self.interval = interval

    def stream(self, n: int = 5):
        """Yield (payload, ts_us) tuples — 50% bookTicker, 50% kline closed."""
        for i in range(n):
            sym = self.symbols[i % len(self.symbols)]
            ts_us = int(time.time() * 1_000_000) + i * 1000
            if i % 2 == 0:
                yield _bookticker_payload(sym), ts_us
            else:
                # kline closed
                price = 100.0 + (i * 0.7)
                yield _kline_ws_payload(sym, interval=self.interval, price=price), ts_us

    def bookticker_stream(self, n: int = 5):
        for i in range(n):
            sym = self.symbols[i % len(self.symbols)]
            yield _bookticker_payload(sym), int(time.time() * 1_000_000)

    def kline_stream(self, n: int = 5):
        for i in range(n):
            sym = self.symbols[i % len(self.symbols)]
            yield _kline_ws_payload(sym, interval=self.interval, price=100 + i), int(time.time() * 1_000_000)


__all__ = [
    "FakeBinanceUMAdapter",
    "FakeBinanceCMAdapter",
    "FakeBybitAdapter",
    "FakeOKXAdapter",
    "FakeHyperliquidAdapter",
    "FAKE_ADAPTERS",
    "get_fake_adapter",
    "FakeWSHarness",
    "_synthetic_klines",
    "_bookticker_payload",
    "_kline_ws_payload",
]
