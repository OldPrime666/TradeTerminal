"""Hyperliquid adapter. Free, no key.
Endpoints:
POST https://api.hyperliquid.xyz/info  {"type":"meta"}
GET not needed; we use POST.

For EVM chains, but for futures chain.
"""
from typing import List, Dict, Any
from decimal import Decimal
from .base import BaseVenueAdapter
import httpx

class HyperliquidAdapter(BaseVenueAdapter):
    venue_id = "hyperliquid"
    rest_base = "https://api.hyperliquid.xyz"
    ws_base = "wss://api.hyperliquid.xyz/ws"
    requests_per_min = 1200

    def ping(self) -> bool:
        # use info meta ping
        r = self._client.post(f"{self.rest_base}/info", json={"type":"meta"}, timeout=self.timeout)
        r.raise_for_status()
        return True

    def get_time(self) -> int:
        # Hyperliquid does not have dedicated time; use local? fall back to 0
        # Try via /info l2Book?
        return 0

    def fetch_contracts(self) -> List[Dict[str, Any]]:
        r = self._client.post(f"{self.rest_base}/info", json={"type":"meta"}, timeout=self.timeout, headers={"Content-Type":"application/json"})
        r.raise_for_status()
        data = r.json()
        return self.parse_meta(data)

    @staticmethod
    def parse_meta(data: Dict[str, Any], venue: str = "hyperliquid") -> List[Dict[str, Any]]:
        # data has "universe": [{"name":"BTC","szDecimals":5, "maxLeverage":50, ...}]
        # or {"universe": [...]} directly
        universe = []
        if isinstance(data, dict):
            universe = data.get("universe") or data.get("meta", {}).get("universe") or []
        elif isinstance(data, list):
            universe = data
        out: List[Dict[str, Any]] = []
        for item in universe:
            name = item.get("name")
            if not name:
                continue
            symbol = f"{name}-PERP" if not name.endswith("PERP") else name  # Hyperliquid uses e.g., BTC
            # hyperliquid symbols are like BTC, but we map to BTC-PERP for registry; underlying is name
            base = name
            quote = "USDC"  # Hyperliquid USDC margined
            settle = "USDC"
            out.append({
                "venue": venue,
                "symbol": symbol,
                "base": base,
                "quote": quote,
                "settle_asset": settle,
                "contract_family": "LINEAR",
                "contract_type": "PERPETUAL",
                "status": "TRADING",
                "tick_size": None,
                "step_size": Decimal(str(10 ** (-item.get("szDecimals", 5)))) if item.get("szDecimals") is not None else None,
                "min_notional": None,
                "margin_asset": settle,
                "asset_class": "CRYPTO",
                "underlying": base,
                "max_leverage": item.get("maxLeverage"),
            })
        return out
