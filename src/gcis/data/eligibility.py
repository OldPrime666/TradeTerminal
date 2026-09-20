"""
Trade eligibility filter — OD criteria per config trade_eligibility + universe.
Filters: min_24h_quote_volume_usdt 5M, max_spread_bps 15, min_listing_age_days 14, min_open_interest_usdt 1M
Deterministic, uses contract registry + 24h stats stub.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

def is_eligible(contract: Dict[str,Any], stats_24h: Dict[str,Any] | None, now: datetime | None =None, config: dict | None =None) -> Dict[str,Any]:
    if now is None:
        now = datetime.now(timezone.utc)
    if config is None:
        try:
            from gcis.core.config import get_config
            config = get_config()
        except:
            config = {}
    elig_cfg = config.get("trade_eligibility", {"min_24h_quote_volume_usdt":5000000,"max_spread_bps":15,"min_listing_age_days":14,"min_open_interest_usdt":1000000}) if config else {"min_24h_quote_volume_usdt":5000000,"max_spread_bps":15,"min_listing_age_days":14,"min_open_interest_usdt":1000000}
    reasons=[]
    ok=True
    # volume
    vol = stats_24h.get("quote_volume", 0) if stats_24h else 0
    if vol < elig_cfg.get("min_24h_quote_volume_usdt",5000000):
        reasons.append(f"VOL {vol}<{elig_cfg.get('min_24h_quote_volume_usdt')}")
        ok=False
    # spread
    spread = stats_24h.get("spread_bps", 0) if stats_24h else 0
    if spread > elig_cfg.get("max_spread_bps",15):
        reasons.append(f"SPREAD {spread}>{elig_cfg.get('max_spread_bps')}")
        ok=False
    # listing age (contract listing_time)
    listing = contract.get("listing_time") or contract.get("listed_at")
    if listing:
        try:
            if isinstance(listing, str):
                lt = datetime.fromisoformat(listing)
            else:
                lt = listing
            if lt.tzinfo is None:
                lt = lt.replace(tzinfo=timezone.utc)
            age_days = (now - lt).total_seconds()/86400
            if age_days < elig_cfg.get("min_listing_age_days",14):
                reasons.append(f"AGE {age_days:.1f}<{elig_cfg.get('min_listing_age_days')}")
                ok=False
        except: pass
    # open interest
    oi = stats_24h.get("open_interest_usdt", stats_24h.get("open_interest", 0)) if stats_24h else 0
    if oi and oi < elig_cfg.get("min_open_interest_usdt",1000000):
        reasons.append(f"OI {oi}<{elig_cfg.get('min_open_interest_usdt')}")
        ok=False
    # status TRADING required
    if contract.get("status") != "TRADING":
        reasons.append(f"STATUS {contract.get('status')} != TRADING")
        ok=False
    return {"eligible": ok, "reasons": reasons, "contract": contract.get("symbol"), "stats": stats_24h}

def filter_eligible(contracts: List[Dict[str,Any]], stats_map: Dict[str, Dict[str,Any]], now: datetime | None =None, config: dict | None =None) -> Dict[str,Any]:
    eligible=[]
    ineligible=[]
    for c in contracts:
        sym = c.get("symbol")
        stats = stats_map.get(sym) if stats_map else None
        res = is_eligible(c, stats, now, config)
        if res["eligible"]:
            eligible.append(c)
        else:
            ineligible.append({"contract": c, "reasons": res["reasons"]})
    return {"eligible": eligible, "ineligible": ineligible, "eligible_count": len(eligible), "total": len(contracts), "ineligible_count": len(ineligible)}
