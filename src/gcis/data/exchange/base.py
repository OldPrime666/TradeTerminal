"""Base contract for venue adapters (DAT-03, INV-03, INV-14). All adapters are free-only, no auth."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import httpx

class BaseVenueAdapter(ABC):
    venue_id: str = "unknown"
    rest_base: str = ""
    ws_base: str = ""
    # rate limits for gateway
    requests_per_min: int = 1200

    def __init__(self, rest_base: str | None = None, ws_base: str | None = None, timeout: int = 10):
        if rest_base:
            self.rest_base = rest_base
        if ws_base:
            self.ws_base = ws_base
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout, headers={"User-Agent": "GCIS/0.1"})

    def close(self):
        try:
            self._client.close()
        except Exception:
            pass

    @abstractmethod
    def fetch_contracts(self) -> List[Dict[str, Any]]:
        """Return normalized contracts. Each dict: symbol, base, quote, settle_asset, family, contract_type, status, tick_size, step_size, margin_asset, asset_class, venue"""
        raise NotImplementedError

    def ping(self) -> bool:
        raise NotImplementedError

    def get_time(self) -> int:
        """Return server time in microseconds UTC µs"""
        raise NotImplementedError

    def _detect_geo_block(self, exc: Exception) -> bool:
        """True if exc indicates 451/403 geo block -> must not circumvent (SEC-09)."""
        msg = str(exc).lower()
        if "451" in msg or "403" in msg or "restricted" in msg or "unavailable for legal" in msg:
            return True
        if hasattr(exc, "response") and getattr(exc, "response") is not None:
            try:
                code = exc.response.status_code  # type: ignore
                if code in (451, 403):
                    return True
            except Exception:
                pass
        return False
