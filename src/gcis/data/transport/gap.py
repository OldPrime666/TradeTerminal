"""
Gap detection + backfill (DAT-05, DAT-10 tail) — detects missing bars and backfills via REST.
"""
from typing import List, Dict, Any, Tuple
import logging
from datetime import datetime, timezone
import pandas as pd
from gcis.data.quality.report import TIMEFRAME_US

log = logging.getLogger(__name__)

def detect_missing_intervals(
    existing_open_times_us: List[int],
    expected_start_us: int,
    expected_end_us: int,
    interval_us: int,
) -> List[Tuple[int,int]]:
    """
    Given sorted existing open_times, return missing intervals [start,end) in us where bars missing.
    Each missing interval is contiguous missing bars.
    """
    if not existing_open_times_us:
        return [(expected_start_us, expected_end_us - interval_us)]
    existing = sorted(set(existing_open_times_us))
    gaps: List[Tuple[int,int]] = []
    # check before first
    if existing[0] > expected_start_us:
        gaps.append((expected_start_us, min(existing[0], expected_end_us)))
    # between
    for i in range(1, len(existing)):
        prev = existing[i-1]
        cur = existing[i]
        diff = cur - prev
        if diff > interval_us * 1.1:  # missed at least one
            # missing from prev+interval to cur
            gaps.append((prev + interval_us, cur))
    # after last
    last = existing[-1]
    if last + interval_us < expected_end_us:
        gaps.append((last + interval_us, expected_end_us))
    return gaps

def backfill_missing(
    venue: str,
    symbol: str,
    timeframe: str,
    gaps: List[Tuple[int,int]],
    max_bars: int = 1500,
    timeout: int = 10,
) -> List[Dict[str, Any]]:
    """
    For each gap, fetch up to max_bars via REST klines. Returns rows to ingest.
    Respects max_bars per DAT-06 / transport.gap_backfill_max_bars.
    """
    if not gaps:
        return []
    interval = TIMEFRAME_US[timeframe]
    rows: List[Dict[str, Any]] = []
    # we only backfill first gap up to max_bars to avoid huge fetch in one go (spec says incremental)
    # For P03, simple: fetch first gap start with limit min(gap_len/interval, max_bars)
    from gcis.data.transport.polling import poll_klines
    # Actually poll_klines does per-symbol limit; we need startTime-based fetch
    # Use adapter directly with startTime
    try:
        if venue != "binance_um":
            return []
        from gcis.data.exchange.binance_um import BinanceUMAdapter
        from gcis.data.archive.store import normalize_timestamp_to_us
        adapter = BinanceUMAdapter(timeout=timeout)
        for gap_start, gap_end in gaps[:1]:  # only first gap per call (incremental)
            gap_bars = (gap_end - gap_start) // interval + 1
            limit = min(gap_bars, max_bars)
            # Binance expects startTime ms; convert gap_start us to ms
            start_ms = gap_start // 1000
            try:
                klines = adapter.klines(symbol, interval=timeframe, limit=limit, startTime=start_ms)
                for k in klines:
                    try:
                        ot = normalize_timestamp_to_us(int(k[0]))
                        ct = normalize_timestamp_to_us(int(k[6]))
                        # only include if within gap
                        if gap_start <= ot <= gap_end:
                            rows.append({
                                "venue": venue,
                                "symbol": symbol,
                                "timeframe": timeframe,
                                "open_time": ot,
                                "close_time": ct,
                                "open": k[1],
                                "high": k[2],
                                "low": k[3],
                                "close": k[4],
                                "volume": k[5],
                                "quote_volume": k[7] if len(k) >7 else None,
                                "trade_count": int(k[8]) if len(k)>8 and k[8] else None,
                                "taker_buy_volume": k[9] if len(k)>9 else None,
                            })
                    except Exception:
                        continue
            except Exception as e:
                log.warning(f"backfill {symbol} {timeframe} gap {gap_start} failed: {e}")
                continue
        adapter.close()
    except Exception as e:
        log.warning(f"backfill setup failed: {e}")
    return rows

def should_trigger_backfill(gap_count: int, disconnected_duration_s: float, max_bars: int = 1500) -> bool:
    """
    Trigger backfill when gap_count>0 or disconnected > polling interval.
    """
    return gap_count > 0 or disconnected_duration_s > 5
