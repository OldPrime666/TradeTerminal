"""
Quality report (DAT-14) — gap detection, missing bars, staleness, AGGREGATION_MISMATCH check.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple
import pandas as pd
import logging

log = logging.getLogger(__name__)

TIMEFRAME_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}

TIMEFRAME_US = {k: v*1000 for k,v in TIMEFRAME_MS.items()}

def expected_bar_count(timeframe: str, start_us: int, end_us: int) -> int:
    interval = TIMEFRAME_US[timeframe]
    # inclusive start exclusive end?
    span = end_us - start_us
    return max(0, span // interval)

def detect_gaps(df: pd.DataFrame, timeframe: str) -> List[Tuple[int,int]]:
    """
    df must have open_time as datetime UTC or int us.
    Returns list of (gap_start_us, gap_end_us) where missing bars >1 interval.
    """
    if df.empty:
        return []
    # normalize to int us
    if pd.api.types.is_datetime64_any_dtype(df["open_time"]):
        times = pd.to_datetime(df["open_time"], utc=True).astype("int64") // 1000  # ns -> us
    else:
        times = df["open_time"].astype("int64")
    times = sorted(times)
    interval = TIMEFRAME_US[timeframe]
    gaps = []
    for i in range(1, len(times)):
        diff = times[i] - times[i-1]
        if diff > interval * 1.1:  # allow small jitter
            # missing bars = diff/interval -1
            gaps.append((times[i-1] + interval, times[i] - interval))
    return gaps

def quality_report(
    venue: str,
    symbol: str,
    timeframe: str,
    df: pd.DataFrame,
    expected_start_us: int | None = None,
    expected_end_us: int | None = None,
) -> Dict[str, Any]:
    """
    Returns report dict: total_bars, expected, missing, gap_count, first_open, last_close, gaps sample, status
    status: OK, GAP, INSUFFICIENT_HISTORY
    """
    if df.empty:
        return {
            "venue": venue,
            "symbol": symbol,
            "timeframe": timeframe,
            "total_bars": 0,
            "expected": 0,
            "missing": 0,
            "gap_count": 0,
            "gaps": [],
            "first_open": None,
            "last_close": None,
            "status": "NO DATA",
        }
    total = len(df)
    # Determine range
    if pd.api.types.is_datetime64_any_dtype(df["open_time"]):
        first = pd.to_datetime(df["open_time"].min(), utc=True)
        last = pd.to_datetime(df["open_time"].max(), utc=True)
        first_us = int(first.timestamp() * 1_000_000)
        last_us = int(last.timestamp() * 1_000_000) + TIMEFRAME_US[timeframe]
    else:
        first_us = int(df["open_time"].min())
        last_us = int(df["open_time"].max()) + TIMEFRAME_US[timeframe]
    if expected_start_us is not None:
        first_us = expected_start_us
    if expected_end_us is not None:
        last_us = expected_end_us
    expected = expected_bar_count(timeframe, first_us, last_us) if expected_start_us else total
    # gaps
    gaps = detect_gaps(df, timeframe)
    # If expected given, missing = expected - total else = len gaps aggregated?
    if expected_start_us is not None:
        missing = max(0, expected - total)
    else:
        # estimate missing from gaps: sum gap spans / interval
        missing = 0
        for gs, ge in gaps:
            span = ge - gs + TIMEFRAME_US[timeframe]
            missing += max(0, span // TIMEFRAME_US[timeframe])
    status = "OK"
    if gaps:
        status = "GAP"
    if total < 300:  # min_history_bars_to_analyse
        status = "INSUFFICIENT_HISTORY"
    # sample gaps as iso strings
    gap_samples = []
    for gs, ge in gaps[:3]:
        gap_samples.append({
            "from": datetime.fromtimestamp(gs/1_000_000, tz=timezone.utc).isoformat(),
            "to": datetime.fromtimestamp(ge/1_000_000, tz=timezone.utc).isoformat(),
            "missing_bars": (ge-gs)//TIMEFRAME_US[timeframe] + 1 if timeframe in TIMEFRAME_US else 0,
        })
    return {
        "venue": venue,
        "symbol": symbol,
        "timeframe": timeframe,
        "total_bars": total,
        "expected": expected,
        "missing": missing,
        "gap_count": len(gaps),
        "gaps_sample": gap_samples,
        "first_open": datetime.fromtimestamp(first_us/1_000_000, tz=timezone.utc).isoformat() if first_us else None,
        "last_close": datetime.fromtimestamp(last_us/1_000_000, tz=timezone.utc).isoformat() if last_us else None,
        "status": status,
    }

def check_aggregation_mismatch(df_1m: pd.DataFrame, df_htf: pd.DataFrame, htf: str) -> Dict[str, Any]:
    """
    Derive HTF from 1m and compare to venue HTF (if provided). For P02 we just check internal derivation error ==0.
    In real P02, we would compare derived vs REST HTF and flag AGGREGATION_MISMATCH if differs > tick.
    """
    from gcis.data.archive.store import derive_timeframe
    derived = derive_timeframe(df_1m, htf)
    if df_htf.empty or derived.empty:
        return {"mismatch": False, "reason": "NO DATA to compare"}
    # Compare close prices for overlapping bars
    # Align on open_time
    merged = pd.merge(derived, df_htf, on="open_time", suffixes=("_derived","_venue"), how="inner")
    if merged.empty:
        return {"mismatch": False, "reason": "no overlapping bars"}
    # Check close diff > tick (use absolute)
    diff = (merged["close_derived"].astype(float) - merged["close_venue"].astype(float)).abs()
    max_diff = diff.max() if not diff.empty else 0
    mismatch = max_diff > 1e-6  # tick tolerance
    return {"mismatch": bool(mismatch), "max_diff": float(max_diff), "overlapping": len(merged)}
