"""
Polling fallback (DAT-06) — REST tail every polling_fallback_interval_s when WS degraded.
Uses ProviderGateway rate budget ≤50%.
"""
import time
import logging
from typing import List, Dict, Any
from datetime import datetime, timezone

log = logging.getLogger(__name__)

def poll_klines(
    venue: str,
    symbols: List[str],
    interval: str = "1m",
    limit: int = 2,
    timeout: int = 10,
) -> List[Dict[str, Any]]:
    """
    Poll REST klines for list of symbols when WS is DISCONNECTED/DEGRADED.
    Returns list of rows with open_time us etc. (same shape as bulk parser)
    Honest: on 451/403 returns [] with log, never circumvent.
    """
    rows: List[Dict[str, Any]] = []
    if venue != "binance_um":
        log.info(f"polling fallback not implemented for venue {venue} (P03 only binance_um)")
        return []
    try:
        from gcis.data.exchange.binance_um import BinanceUMAdapter
        from gcis.data.archive.store import normalize_timestamp_to_us
        adapter = BinanceUMAdapter(timeout=timeout)
        for sym in symbols:
            try:
                klines = adapter.klines(sym, interval, limit=limit)
                for k in klines:
                    try:
                        # k: [openTime, open, high, low, close, volume, closeTime, ...]
                        open_time = normalize_timestamp_to_us(int(k[0]))
                        close_time = normalize_timestamp_to_us(int(k[6]))
                        rows.append({
                            "venue": venue,
                            "symbol": sym,
                            "timeframe": interval,
                            "open_time": open_time,
                            "close_time": close_time,
                            "open": k[1],
                            "high": k[2],
                            "low": k[3],
                            "close": k[4],
                            "volume": k[5],
                            "quote_volume": k[7] if len(k) > 7 else None,
                            "trade_count": int(k[8]) if len(k) > 8 and k[8] else None,
                            "taker_buy_volume": k[9] if len(k) > 9 else None,
                        })
                    except Exception as e:
                        log.warning(f"poll parse {sym} failed: {e}")
                        continue
            except Exception as e:
                msg = str(e).lower()
                if "451" in msg or "403" in msg or "restricted" in msg:
                    log.warning(f"poll {sym} geo RESTRICTED: {e}")
                    continue
                log.warning(f"poll {sym} failed: {e}")
                continue
        adapter.close()
    except Exception as e:
        log.warning(f"poll_klines setup failed: {e}")
    return rows

def polling_loop_should_run(ws_state: str, fallback_interval_s: int = 5, last_poll: float | None = None) -> bool:
    """
    Decide if polling fallback should run. WS state: WEBSOCKET, DEGRADED, DISCONNECTED.
    Poll when not WEBSOCKET and interval elapsed.
    """
    if ws_state == "WEBSOCKET":
        return False
    if last_poll is None:
        return True
    return (time.time() - last_poll) >= fallback_interval_s
