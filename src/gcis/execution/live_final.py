"""Live final wiring — P22 last feature: CCXT live stub with free-only check."""
from typing import Dict, Any

def ccxt_live_status(mode: str = "stub") -> Dict[str,Any]:
    """
    Returns CCXT live status. Free-only: no API keys, stub mode default.
    When mode='live' requires env keys but we stay stub for free tier.
    """
    if mode == "stub":
        return {"ok": True, "mode": "stub", "venue": "binanceusdm", "note": "free stub — no keys, paper+backtest only"}
    if mode == "live":
        return {"ok": False, "mode": "live", "reason": "keys_required", "note": "live requires API keys — not used in free P22"}
    return {"ok": False, "reason": "unknown_mode"}

def bundle_budget_check(bundle_ms: int, limit_ms: int = 20000) -> Dict[str,Any]:
    """
    Bundle budget check ARC-20: 20s limit.
    """
    ok = bundle_ms <= limit_ms
    return {"ok": ok, "bundle_ms": bundle_ms, "limit_ms": limit_ms, "status": "PASS" if ok else "FAIL", "note": "ARC-20 20s bundle budget"}
