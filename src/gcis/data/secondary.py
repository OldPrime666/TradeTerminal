"""
DAT-12 secondary (metadata only, never overwrite candle).
Compares canonical vs secondary price, reports discrepancy but never overwrites.
Config discrepancy: warn 30 bps flag 100, only_compare_when_both_fresher_than_s 900
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional

WARN_BPS = 30
FLAG_BPS = 100
FRESH_S = 900

def bps_diff(price_a: float, price_b: float) -> float:
    if price_a == 0:
        return 0.0
    # Use Decimal for precise bps to avoid float 29.999 edge on 100.3
    from decimal import Decimal
    try:
        a = Decimal(str(price_a))
        b = Decimal(str(price_b))
        return float(abs(a - b) / a * Decimal("10000"))
    except Exception:
        return abs(price_a - price_b) / price_a * 10000.0

def is_fresh(ts: datetime, now: datetime, threshold_s: int = FRESH_S) -> bool:
    if ts is None:
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age = (now - ts).total_seconds()
    return age <= threshold_s

def check_discrepancy(
    canonical_price: float,
    secondary_price: float,
    canonical_time: datetime,
    secondary_time: datetime,
    now: Optional[datetime] = None,
    warn_bps: int = WARN_BPS,
    flag_bps: int = FLAG_BPS,
    only_compare_when_both_fresher_than_s: int = FRESH_S,
) -> Dict[str, Any]:
    """
    DAT-12: compares prices if both fresh, returns status OK/WARN/FLAG and bps diff.
    Never overwrites canonical (candle) — metadata only.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    # freshness gate
    can_fresh = is_fresh(canonical_time, now, only_compare_when_both_fresher_than_s)
    sec_fresh = is_fresh(secondary_time, now, only_compare_when_both_fresher_than_s)
    if not can_fresh or not sec_fresh:
        return {
            "status": "STALE_SKIP",
            "bps": None,
            "canonical_fresh": can_fresh,
            "secondary_fresh": sec_fresh,
            "action": "SKIP",
            "note": "DAT-12 metadata only: skip when not both fresh <=900s"
        }
    bps = bps_diff(canonical_price, secondary_price)
    if bps >= flag_bps:
        status = "FLAG"
        action = "MARKET_DATA_DISCREPANCY"
    elif bps >= warn_bps:
        status = "WARN"
        action = "LOG_ONLY"
    else:
        status = "OK"
        action = "NONE"
    return {
        "status": status,
        "bps": round(float(bps), 2),
        "canonical_price": float(canonical_price),
        "secondary_price": float(secondary_price),
        "warn_bps": warn_bps,
        "flag_bps": flag_bps,
        "action": action,
        "overwrite": False,  # never overwrite per DAT-12
        "note": "DAT-12 secondary metadata only, never overwrites candle."
    }

def fetch_secondary_meta(symbol: str, source: str = "coinpaprika") -> Dict[str,Any]:
    """
    Stub for secondary metadata fetch (free-only, keyless per CAP). For P14, returns mock structure without network.
    In live run, would call coinpaprika etc via sources.yaml with budget, but never overwrites.
    """
    # Placeholder honest: no live secondary until configured; return UNAVAILABLE
    return {
        "symbol": symbol,
        "source": source,
        "price": None,
        "timestamp": None,
        "status": "UNAVAILABLE",
        "note": "DAT-12 secondary fetch disabled until budgets allow; metadata only."
    }
