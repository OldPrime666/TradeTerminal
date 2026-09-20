"""
src/gcis/data/time_sync.py — Venue time sync (DAT-??, CAP-14) Free, no key.
Primary: venue /fapi/v1/time (Binance) /api/v5/public/time (OKX) -> µs
Fallbacks: NTP pool, HTTP Date header
Never fabricate: if all fail -> CLOCK_DRIFT unknown, blocks entries (INV-10 via clock).
"""
from typing import Optional, Tuple
import time
import logging

log = logging.getLogger(__name__)

def get_venue_time(venue: str = "binance_um", timeout: int = 5) -> Optional[int]:
    """Return server time µs or None. Uses adapter get_time()."""
    try:
        if venue == "binance_um":
            from gcis.data.exchange.binance_um import BinanceUMAdapter
            a = BinanceUMAdapter(timeout=timeout)
            t = a.get_time()
            a.close()
            return t
        if venue == "binance_cm":
            from gcis.data.exchange.binance_cm import BinanceCMAdapter
            a = BinanceCMAdapter(timeout=timeout)
            t = a.get_time()
            a.close()
            return t
        if venue.startswith("bybit"):
            from gcis.data.exchange.bybit import BybitAdapter
            a = BybitAdapter(timeout=timeout)
            t = a.get_time()
            a.close()
            return t
        if venue.startswith("okx"):
            from gcis.data.exchange.okx import OKXAdapter
            a = OKXAdapter(timeout=timeout)
            t = a.get_time()
            a.close()
            return t
        # hyperliquid no time endpoint -> None
        return None
    except Exception as e:
        log.warning(f"time_sync venue {venue} failed: {e}")
        return None

def get_ntp_time(timeout: int = 5) -> Optional[int]:
    try:
        import ntplib
        client = ntplib.NTPClient()
        resp = client.request('pool.ntp.org', version=3, timeout=timeout)
        # resp.tx_time is seconds since epoch
        return int(resp.tx_time * 1_000_000)
    except Exception as e:
        log.debug(f"NTP failed: {e}")
        return None

def get_http_date_time(timeout: int = 5) -> Optional[int]:
    try:
        import httpx, email.utils
        r = httpx.get("https://www.google.com/generate_204", timeout=timeout, follow_redirects=False)
        date_hdr = r.headers.get("Date")
        if date_hdr:
            dt = email.utils.parsedate_to_datetime(date_hdr)
            return int(dt.timestamp() * 1_000_000)
        return None
    except Exception as e:
        log.debug(f"HTTP Date failed: {e}")
        return None

def sync_time(venue_chain=None, timeout: int = 5) -> Tuple[Optional[int], str]:
    """
    Try venue time in order, then NTP, then HTTP Date.
    Returns (time_us, source) or (None, "NO DATA")
    """
    from gcis.core.config import get_config
    if venue_chain is None:
        venue_chain = get_config().get("universe", {}).get("venue_chain", ["binance_um","bybit_linear","okx_swap"])
    for venue in venue_chain:
        t = get_venue_time(venue, timeout=timeout)
        if t:
            log.info(f"time_sync: venue {venue} -> {t}")
            return t, f"venue:{venue}"
    # NTP fallback
    t = get_ntp_time(timeout=timeout)
    if t:
        return t, "ntp"
    t = get_http_date_time(timeout=timeout)
    if t:
        return t, "http_date"
    return None, "NO DATA"

def clock_drift_ms(server_time_us: Optional[int]) -> Optional[int]:
    if server_time_us is None:
        return None
    import time as _time
    local_us = int(_time.time() * 1_000_000)
    return int((local_us - server_time_us) / 1000)
