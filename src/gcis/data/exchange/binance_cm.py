"""Binance COIN-M Futures adapter (chain #1b). Endpoint https://dapi.binance.com/dapi/v1/exchangeInfo"""
from typing import List, Dict, Any
from decimal import Decimal
from .base import BaseVenueAdapter

class BinanceCMAdapter(BaseVenueAdapter):
    venue_id = "binance_cm"
    rest_base = "https://dapi.binance.com"
    ws_base = "wss://dstream.binance.com"
    requests_per_min = 2400

    def ping(self) -> bool:
        r = self._client.get(f"{self.rest_base}/dapi/v1/ping", timeout=self.timeout)
        r.raise_for_status()
        return True

    def get_time(self) -> int:
        r = self._client.get(f"{self.rest_base}/dapi/v1/time", timeout=self.timeout)
        r.raise_for_status()
        ts = r.json().get("serverTime")
        return int(ts * 1000)

    def fetch_contracts(self) -> List[Dict[str, Any]]:
        url = f"{self.rest_base}/dapi/v1/exchangeInfo"
        r = self._client.get(url, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        return self.parse_exchange_info(data)

    @staticmethod
    def parse_exchange_info(data: Dict[str, Any], venue: str = "binance_cm") -> List[Dict[str, Any]]:
        symbols = data.get("symbols", [])
        out: List[Dict[str, Any]] = []
        for s in symbols:
            symbol = s.get("symbol")
            if not symbol:
                continue
            base = s.get("baseAsset") or ""
            quote = s.get("quoteAsset") or ""
            ctype_raw = s.get("contractType", "PERPETUAL")
            ctype_map = {"PERPETUAL": "PERPETUAL", "CURRENT_QUARTER": "DELIVERY_CURRENT", "NEXT_QUARTER": "DELIVERY_NEXT"}
            ctype = ctype_map.get(ctype_raw, "OTHER")
            status = s.get("contractStatus") or s.get("status") or "UNKNOWN"
            status = "TRADING" if status == "TRADING" else status
            filters = s.get("filters", [])
            tick = None
            step = None
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
            settle = s.get("marginAsset") or base  # coin-margined uses base
            out.append({
                "venue": venue,
                "symbol": symbol,
                "base": base,
                "quote": quote,
                "settle_asset": settle,
                "contract_family": "INVERSE",
                "contract_type": ctype,
                "status": status,
                "tick_size": tick,
                "step_size": step,
                "min_notional": None,
                "margin_asset": settle,
                "asset_class": "CRYPTO",
                "underlying": base,
            })
        return out
