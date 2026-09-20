"""OKX SWAP/FUTURES adapter. Free, no key.
Endpoints:
GET /api/v5/public/instruments?instType=SWAP
GET /api/v5/public/instruments?instType=FUTURES
"""
from typing import List, Dict, Any
from decimal import Decimal
from .base import BaseVenueAdapter

class OKXAdapter(BaseVenueAdapter):
    venue_id = "okx_swap"
    rest_base = "https://www.okx.com"
    ws_base = "wss://ws.okx.com:8443/ws/v5/public"
    requests_per_min = 1200

    def ping(self) -> bool:
        r = self._client.get(f"{self.rest_base}/api/v5/public/time", timeout=self.timeout)
        r.raise_for_status()
        return True

    def get_time(self) -> int:
        r = self._client.get(f"{self.rest_base}/api/v5/public/time", timeout=self.timeout)
        r.raise_for_status()
        data = r.json().get("data", [])
        if data:
            ts = int(data[0].get("ts", 0))
            # ts is ms
            return ts * 1000
        return 0

    def fetch_contracts(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for instType in ("SWAP", "FUTURES"):
            url = f"{self.rest_base}/api/v5/public/instruments"
            params = {"instType": instType}
            r = self._client.get(url, params=params, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
            out.extend(self.parse_instruments(data, instType))
        return out

    @staticmethod
    def parse_instruments(data: Dict[str, Any], instType: str = "SWAP", venue: str = "okx_swap") -> List[Dict[str, Any]]:
        rows = data.get("data", [])
        out: List[Dict[str, Any]] = []
        for s in rows:
            instId = s.get("instId") or s.get("instid")
            if not instId:
                continue
            base = s.get("baseCcy") or s.get("uly", "").split("-")[0] if s.get("uly") else ""
            quote = s.get("quoteCcy") or ""
            settle = s.get("settleCcy") or ""
            # ctType linear/inverse, instType SWAP/FUTURES
            ctType = s.get("ctType") or s.get("ctValCcy", "")
            # family: linear if settle == quote (USDT margined), inverse if settle == base
            family = "LINEAR"
            if ctType == "inverse" or (settle and base and settle == base):
                family = "INVERSE"
            elif ctType == "linear":
                family = "LINEAR"
            else:
                # default by settle
                if settle and quote and settle == quote:
                    family = "LINEAR"
            state = s.get("state") or ""
            status = "TRADING" if state == "live" else state.upper() if state else "UNKNOWN"
            ctype = "PERPETUAL" if instType == "SWAP" else "DELIVERY_CURRENT"
            tick = None
            step = None
            try:
                if s.get("tickSz"):
                    tick = Decimal(str(s["tickSz"]))
                if s.get("lotSz"):
                    step = Decimal(str(s["lotSz"]))
            except Exception:
                pass
            out.append({
                "venue": venue,
                "symbol": instId,
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
