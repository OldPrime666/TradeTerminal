"""Bybit Linear/Inverse adapter. Free, no key. Endpoints:
GET /v5/market/instruments-info?category=linear
GET /v5/market/instruments-info?category=inverse
"""
from typing import List, Dict, Any
from decimal import Decimal
from .base import BaseVenueAdapter

CATEGORY_MAP = {
    "linear": "LINEAR",
    "inverse": "INVERSE",
}

class BybitAdapter(BaseVenueAdapter):
    venue_id = "bybit_linear"  # primary; inverse handled same class with category param
    rest_base = "https://api.bybit.com"
    ws_base = "wss://stream.bybit.com"
    requests_per_min = 600  # conservative (600/5s -> 120/min? we cap 600/min)

    def ping(self) -> bool:
        r = self._client.get(f"{self.rest_base}/v5/market/time", timeout=self.timeout)
        r.raise_for_status()
        return True

    def get_time(self) -> int:
        r = self._client.get(f"{self.rest_base}/v5/market/time", timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        # {"result":{"timeSecond":"171...","timeNano":"..."},"time":...}
        # timeNano is ns, fallback to timeSecond
        try:
            nano = int(data.get("result", {}).get("timeNano") or 0)
            if nano:
                return int(nano // 1000)  # ns -> µs
            sec = int(data.get("result", {}).get("timeSecond") or 0)
            if sec:
                return sec * 1_000_000
            # fallback
            return int(data.get("time", 0) * 1000)  # ms -> µs
        except Exception:
            return 0

    def fetch_contracts(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for category in ("linear", "inverse"):
            url = f"{self.rest_base}/v5/market/instruments-info"
            params = {"category": category}
            r = self._client.get(url, params=params, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
            out.extend(self.parse_instruments_info(data, category))
        return out

    @staticmethod
    def parse_instruments_info(data: Dict[str, Any], category: str = "linear", venue: str = "bybit_linear") -> List[Dict[str, Any]]:
        lst = data.get("result", {}).get("list", []) or data.get("result", {}).get("symbolList", []) or []
        out: List[Dict[str, Any]] = []
        family = CATEGORY_MAP.get(category, "LINEAR")
        # inverse venue variant
        venue_id = "bybit_inverse" if family == "INVERSE" else "bybit_linear"
        for s in lst:
            symbol = s.get("symbol")
            if not symbol:
                continue
            base = s.get("baseCoin") or s.get("base") or ""
            quote = s.get("quoteCoin") or s.get("quote") or ""
            settle = s.get("settleCoin") or s.get("settle") or quote
            status_raw = s.get("status") or ""
            status = "TRADING" if status_raw == "Trading" else status_raw.upper() if status_raw else "UNKNOWN"
            ctype_raw = s.get("contractType") or s.get("contract_type") or ""
            # LinearPerpetual -> PERPETUAL
            if "Perpetual" in ctype_raw:
                ctype = "PERPETUAL"
            elif "Futures" in ctype_raw:
                ctype = "DELIVERY_CURRENT"  # simplified
            else:
                ctype = "PERPETUAL" if category == "linear" else "PERPETUAL"
            # priceFilter tick
            tick = None
            step = None
            try:
                pf = s.get("priceFilter", {})
                if pf.get("tickSize"):
                    tick = Decimal(str(pf["tickSize"]))
                lf = s.get("lotSizeFilter", {})
                if lf.get("qtyStep"):
                    step = Decimal(str(lf["qtyStep"]))
            except Exception:
                pass
            out.append({
                "venue": venue_id,
                "symbol": symbol,
                "base": base,
                "quote": quote,
                "settle_asset": settle,
                "contract_family": family,
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
