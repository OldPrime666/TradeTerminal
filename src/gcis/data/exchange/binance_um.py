"""Binance USDⓈ-M Futures adapter (primary venues chain). Free, no key (INV-14). Endpoint GET /fapi/v1/exchangeInfo"""
from typing import List, Dict, Any
from decimal import Decimal
from .base import BaseVenueAdapter
import httpx

class BinanceUMAdapter(BaseVenueAdapter):
    venue_id = "binance_um"
    rest_base = "https://fapi.binance.com"
    ws_base = "wss://fstream.binance.com"
    requests_per_min = 2400

    def ping(self) -> bool:
        r = self._client.get(f"{self.rest_base}/fapi/v1/ping", timeout=self.timeout)
        r.raise_for_status()
        return True

    def get_time(self) -> int:
        r = self._client.get(f"{self.rest_base}/fapi/v1/time", timeout=self.timeout)
        r.raise_for_status()
        ts = r.json().get("serverTime")
        # fapi returns ms
        return int(ts * 1000)

    def fetch_contracts(self) -> List[Dict[str, Any]]:
        url = f"{self.rest_base}/fapi/v1/exchangeInfo"
        r = self._client.get(url, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        return self.parse_exchange_info(data)

    def klines(self, symbol: str, interval: str, limit: int = 100, startTime: int | None = None, endTime: int | None = None) -> List[List[Any]]:
        """
        GET /fapi/v1/klines — futures klines. interval like 1m, 5m etc.
        startTime/endTime in ms (Binance expects ms). We handle µs input by converting.
        """
        params: Dict[str, Any] = {"symbol": symbol, "interval": interval, "limit": limit}
        # normalize start/end from µs to ms if needed
        def to_ms(ts):
            if ts is None:
                return None
            if ts > 1_000_000_000_000_000:  # µs
                return ts // 1000
            if ts > 1_000_000_000_000:  # ms already
                return ts
            return ts
        if startTime is not None:
            params["startTime"] = to_ms(startTime)
        if endTime is not None:
            params["endTime"] = to_ms(endTime)
        r = self._client.get(f"{self.rest_base}/fapi/v1/klines", params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def mark_price_klines(self, symbol: str, interval: str, limit: int = 100, startTime: int | None = None) -> List[List[Any]]:
        params: Dict[str, Any] = {"symbol": symbol, "interval": interval, "limit": limit}
        if startTime is not None:
            # convert µs to ms
            params["startTime"] = startTime // 1000 if startTime > 1_000_000_000_000_000 else startTime
        r = self._client.get(f"{self.rest_base}/fapi/v1/markPriceKlines", params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def parse_exchange_info(data: Dict[str, Any], venue: str = "binance_um") -> List[Dict[str, Any]]:
        """Parse Binance UM exchangeInfo JSON into normalized contracts. Handles recorded payloads offline."""
        symbols = data.get("symbols", [])
        out: List[Dict[str, Any]] = []
        for s in symbols:
            symbol = s.get("symbol")
            if not symbol:
                continue
            # family: LINEAR if quote is USDT/USDC/BUSD etc, INVERSE if base-settled? Binance UM is linear USDT margined
            quote = s.get("quoteAsset") or s.get("quoteAsset", "")
            base = s.get("baseAsset") or ""
            # contractType PERPETUAL, CURRENT_QUARTER etc
            ctype_raw = s.get("contractType", "PERPETUAL")
            ctype_map = {"PERPETUAL": "PERPETUAL", "CURRENT_QUARTER": "DELIVERY_CURRENT", "NEXT_QUARTER": "DELIVERY_NEXT", "PERPETUAL_DELIVERING": "PERPETUAL"}
            ctype = ctype_map.get(ctype_raw, "OTHER")
            status_raw = s.get("status") or s.get("contractStatus") or ""
            status = "TRADING" if status_raw in ("TRADING", "TRADING", "TRADING") else status_raw
            # only include TRADING for coverage but keep others for status history
            if not status:
                status = "UNKNOWN"
            # filters for tick/step
            filters = s.get("filters", [])
            tick = None
            step = None
            min_notional = None
            for f in filters:
                if f.get("filterType") == "PRICE_FILTER":
                    try:
                        tick = Decimal(str(f.get("tickSize", "0")))
                    except Exception:
                        tick = None
                if f.get("filterType") == "LOT_SIZE":
                    try:
                        step = Decimal(str(f.get("stepSize", "0")))
                    except Exception:
                        step = None
                if f.get("filterType") in ("MIN_NOTIONAL", "NOTIONAL"):
                    try:
                        min_notional = Decimal(str(f.get("notional", f.get("minNotional", "0"))))
                    except Exception:
                        pass
            settle = s.get("marginAsset") or quote
            # margin asset
            margin_asset = s.get("marginAsset") or quote
            # family: Binance UM always LINEAR (USDT margined). CM would be INVERSE but separate adapter.
            family = "LINEAR"
            # asset_class: default CRYPTO, allow override (tradfi futures like indices?)
            asset_class = "CRYPTO"
            # special: if symbol underlying is equity/index/commodity, would tag via overrides
            out.append({
                "venue": venue,
                "symbol": symbol,
                "base": base,
                "quote": quote,
                "settle_asset": settle,
                "contract_family": family,
                "contract_type": ctype,
                "status": status,
                "tick_size": tick,
                "step_size": step,
                "min_notional": min_notional,
                "margin_asset": margin_asset,
                "asset_class": asset_class,
                # leverage tiers via separate endpoint but placeholder
                "max_leverage": s.get("maxLeverage") or None,
                "underlying": base,
            })
        return out
