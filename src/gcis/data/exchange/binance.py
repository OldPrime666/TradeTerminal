import httpx
from decimal import Decimal
from datetime import datetime, timezone
import time

class BinanceAdapter:
    """
    Native Binance public market data adapter — no auth, free resources only.
    REST base: https://data-api.binance.vision, WS: wss://data-stream.binance.vision
    Implements: exchangeInfo, ping, time, klines, ticker, bookTicker, depth (snapshot), aggTrades
    All via ProviderGateway rate limiting (handled externally but also internal budget).
    """
    def __init__(self, rest_base: str = "https://data-api.binance.vision", timeout: int = 10):
        self.rest_base = rest_base.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout, headers={"User-Agent": "GCIS/0.1"})

    def ping(self):
        r = self._client.get(f"{self.rest_base}/api/v3/ping")
        r.raise_for_status()
        return r.json()

    def get_time(self):
        r = self._client.get(f"{self.rest_base}/api/v3/time", headers={"X-MBX-TIME-UNIT": "MICROSECOND"})
        r.raise_for_status()
        data = r.json()
        # serverTime in microseconds if requested else ms; normalize to µs
        ts = data.get("serverTime")
        # detect digit length
        if ts < 1e12:  # likely seconds? not
            ts = ts * 1000
        elif ts < 1e15:  # ms -> µs
            ts = ts * 1000
        return ts

    def exchange_info(self):
        r = self._client.get(f"{self.rest_base}/api/v3/exchangeInfo")
        r.raise_for_status()
        return r.json()

    def klines(self, symbol: str, interval: str, limit: int = 100, startTime=None, endTime=None):
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime
        r = self._client.get(f"{self.rest_base}/api/v3/klines", params=params)
        r.raise_for_status()
        return r.json()

    def ticker_price(self, symbol: str = None):
        params = {}
        if symbol:
            params["symbol"] = symbol
        r = self._client.get(f"{self.rest_base}/api/v3/ticker/price", params=params)
        r.raise_for_status()
        return r.json()

    def book_ticker(self, symbol: str = None):
        params = {}
        if symbol:
            params["symbol"] = symbol
        r = self._client.get(f"{self.rest_base}/api/v3/ticker/bookTicker", params=params)
        r.raise_for_status()
        return r.json()

    def depth(self, symbol: str, limit: int = 20):
        r = self._client.get(f"{self.rest_base}/api/v3/depth", params={"symbol": symbol, "limit": limit})
        r.raise_for_status()
        return r.json()

    def agg_trades(self, symbol: str, limit: int = 100):
        r = self._client.get(f"{self.rest_base}/api/v3/aggTrades", params={"symbol": symbol, "limit": limit})
        r.raise_for_status()
        return r.json()

    def close(self):
        self._client.close()

def normalize_timestamp(ts: int, source: str = "binance") -> int:
    """
    Normalize ms vs µs to µs integer.
    Spot files >=2025-01-01 are µs, before are ms.
    Live REST with MICROSECOND header returns µs.
    Heuristic: digit length.
    """
    # if ts < 1e12 => seconds -> *1e6
    # if 1e12 <= ts < 1e15 => ms -> *1000
    # else µs
    if ts < 1_000_000_000_000:  # < 1e12
        return int(ts * 1_000_000)
    elif ts < 1_000_000_000_000_000:  # <1e15
        return int(ts * 1000)
    else:
        return int(ts)
