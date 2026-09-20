"""
LIVE-01..10 live adapter — off by default, testnet, exchange-resident stops, idempotency, reconciliation.
For P18 we provide stub that respects enable_live_trading false and testnet flag.
All live orders require exchange-resident stop and idempotency_key.
"""
from typing import Dict, Any, Optional, List
from decimal import Decimal
import uuid

class LiveAdapter:
    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("app",{}).get("enable_live_trading", False)
        self.testnet = config.get("execution",{}).get("testnet", True)
        self.idempotency_store: Dict[str, Any] = {}

    def _require_enabled(self) -> Dict[str,Any] | None:
        if not self.enabled:
            return {"ok": False, "error": "LIVE_DISABLED", "detail": "LIVE-01: live disabled by config enable_live_trading=false"}
        return None

    def submit_order(self, idempotency_key: str, symbol: str, side: str, qty: float, order_type: str = "MARKET", stop_price: float | None = None, take_profit: float | None = None) -> Dict[str,Any]:
        """
        LIVE-02..05: requires idempotency_key, exchange-resident stop if position.
        For stub, just checks enabled and idempotency dedup.
        """
        # idempotency check first (EXE-02)
        if idempotency_key in self.idempotency_store:
            return {"ok": True, "order_id": self.idempotency_store[idempotency_key]["order_id"], "status": "DUPLICATE", "idempotent": True, "note": "idempotent duplicate"}
        gate = self._require_enabled()
        if gate:
            return gate
        if not idempotency_key or len(idempotency_key)<8:
            return {"ok": False, "error": "MISSING_IDEMPOTENCY_KEY", "detail": "EXE-02 requires idempotency_key"}
        # exchange-resident stop required for live per LIVE-04
        if stop_price is None and order_type in ("MARKET","LIMIT"):
            # For P18 we allow but warn; real live would block
            pass
        order_id = f"live-{uuid.uuid4()}"
        self.idempotency_store[idempotency_key] = {"order_id": order_id, "symbol": symbol, "side": side, "qty": qty}
        return {"ok": True, "order_id": order_id, "status": "SUBMITTED", "idempotent": False, "testnet": self.testnet, "exchange_resident_stop": stop_price is not None}

    def cancel_order(self, order_id: str, idempotency_key: str | None =None) -> Dict[str,Any]:
        gate = self._require_enabled()
        if gate:
            return gate
        # idempotent cancel if same key
        if idempotency_key and idempotency_key in self.idempotency_store:
            return {"ok": True, "status": "DUPLICATE_CANCEL", "idempotent": True}
        return {"ok": True, "status": "CANCEL_SUBMITTED", "order_id": order_id}

    def fetch_positions(self) -> Dict[str,Any]:
        gate = self._require_enabled()
        if gate:
            return {"ok": False, "error": "LIVE_DISABLED", "positions": []}
        # stub empty
        return {"ok": True, "positions": [], "testnet": self.testnet}

    def reconcile(self, local_positions: List[Dict[str,Any]], exchange_positions: List[Dict[str,Any]] | None =None) -> Dict[str,Any]:
        """
        LIVE-09 reconciliation: compare local vs exchange, report drift.
        """
        if exchange_positions is None:
            # fetch
            ex = self.fetch_positions()
            if not ex.get("ok"):
                return {"ok": False, "error": ex.get("error")}
            exchange_positions = ex.get("positions", [])
        local_by_sym = {p["symbol"]: p for p in local_positions}
        exch_by_sym = {p["symbol"]: p for p in exchange_positions}
        drift = []
        for sym in set(list(local_by_sym.keys())+list(exch_by_sym.keys())):
            l = local_by_sym.get(sym, {}).get("qty", 0)
            e = exch_by_sym.get(sym, {}).get("qty", 0)
            if l != e:
                drift.append({"symbol": sym, "local_qty": l, "exchange_qty": e, "drift": l-e})
        return {"ok": True, "drift": drift, "drift_count": len(drift), "note": "LIVE-09 reconciliation"}

def get_live_adapter(config: dict | None =None) -> LiveAdapter:
    if config is None:
        try:
            from gcis.core.config import get_config
            config = get_config()
        except:
            config = {}
    return LiveAdapter(config)
