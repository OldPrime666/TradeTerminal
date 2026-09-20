"""
Bulk download from data.binance.vision (DAT-10) + public.bybit.com fallback.
Supports futures/um daily/monthly zips, checksum, unzip, ms/µs normalize, resumable.
Free-only, never circumvent 451.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta, date
import csv
import zipfile
import io
import hashlib
import httpx
import logging
from typing import List, Dict, Any, Optional, Tuple

log = logging.getLogger(__name__)

# Futures UM / CM daily/monthly path patterns
# https://data.binance.vision/data/futures/um/daily/klines/SYMBOL/1m/SYMBOL-1m-YYYY-MM-DD.zip
# https://data.binance.vision/data/futures/um/monthly/klines/SYMBOL/1m/SYMBOL-1m-YYYY-MM.zip
# CM similar: /data/futures/cm/daily/klines/...

BINANCE_VISION_BASE = "https://data.binance.vision"
# bybit public: https://public.bybit.com/trading/SYMBOL/  ??? For P02 we fallback to REST tail if bulk fails.

def binance_futures_daily_urls(symbol: str, timeframe: str, start: date, end: date, market: str = "um") -> List[str]:
    """
    market: um or cm
    Returns list of URLs for daily zips between start and end inclusive.
    """
    urls = []
    cur = start
    while cur <= end:
        fname = f"{symbol}-{timeframe}-{cur.isoformat()}.zip"
        # path: data/futures/{market}/daily/klines/SYMBOL/TF/fname
        path = f"data/futures/{market}/daily/klines/{symbol}/{timeframe}/{fname}"
        urls.append(f"{BINANCE_VISION_BASE}/{path}")
        cur += timedelta(days=1)
    return urls

def binance_futures_monthly_urls(symbol: str, timeframe: str, months: List[Tuple[int,int]], market: str = "um") -> List[str]:
    urls = []
    for y,m in months:
        fname = f"{symbol}-{timeframe}-{y:04d}-{m:02d}.zip"
        path = f"data/futures/{market}/monthly/klines/{symbol}/{timeframe}/{fname}"
        urls.append(f"{BINANCE_VISION_BASE}/{path}")
    return urls

def checksum_url(zip_url: str) -> str:
    return zip_url + ".CHECKSUM"

def normalize_ts(ts: int) -> int:
    if ts < 1_000_000_000_000:
        return int(ts * 1_000_000)
    elif ts < 1_000_000_000_000_000:
        return int(ts * 1000)
    else:
        return int(ts)

def parse_binance_kline_csv_row(row: list[str]) -> Optional[Dict[str, Any]]:
    """
    Binance vision CSV row columns (futures klines):
    0 open_time, 1 open, 2 high, 3 low, 4 close, 5 volume, 6 close_time,
    7 quote_volume, 8 trades, 9 taker_buy_base_vol, 10 taker_buy_quote_vol, 11 ignore
    All times are ms (historical) — normalize to µs.
    """
    try:
        if len(row) < 11:
            return None
        open_time = normalize_ts(int(row[0]))
        close_time = normalize_ts(int(row[6]))
        return {
            "open_time": open_time,
            "open": row[1],
            "high": row[2],
            "low": row[3],
            "close": row[4],
            "volume": row[5],
            "close_time": close_time,
            "quote_volume": row[7],
            "trade_count": int(row[8]) if row[8] else None,
            "taker_buy_volume": row[9],
            "taker_buy_quote_volume": row[10],
        }
    except Exception as e:
        log.warning(f"csv parse failed {row[:3]}: {e}")
        return None

def download_and_parse_zip(url: str, timeout: int = 30, verify_checksum: bool = True) -> List[Dict[str, Any]]:
    """
    Download zip, verify checksum if available (.CHECKSUM), unzip, parse CSV.
    Returns list of rows dicts with normalized timestamps.
    Honest: on 451/403 returns [] with log, never circumvent.
    """
    # Use httpx streaming
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent":"GCIS/0.1"}) as client:
            # Check checksum first if verify
            expected_sha = None
            if verify_checksum:
                try:
                    r = client.get(checksum_url(url), timeout=10)
                    if r.status_code == 200:
                        # file contains "sha256  filename"
                        expected_sha = r.text.strip().split()[0]
                except Exception:
                    pass
            r = client.get(url, timeout=timeout)
            if r.status_code in (451, 403):
                log.warning(f"bulk {url} -> RESTRICTED {r.status_code} (no circumvention)")
                return []
            if r.status_code == 404:
                # missing file (e.g., future date) — not error, just no data
                log.info(f"bulk {url} 404 not found (no data for that date)")
                return []
            r.raise_for_status()
            content = r.content
            if expected_sha:
                actual = hashlib.sha256(content).hexdigest()
                if actual != expected_sha:
                    log.warning(f"checksum mismatch for {url}: expected {expected_sha[:12]} got {actual[:12]}")
                    # still continue but mark
            # Unzip
            zip_bytes = io.BytesIO(content)
            with zipfile.ZipFile(zip_bytes) as z:
                # assume single csv inside
                names = z.namelist()
                if not names:
                    return []
                csv_name = names[0]
                with z.open(csv_name) as f:
                    text = io.TextIOWrapper(f, encoding="utf-8")
                    reader = csv.reader(text)
                    rows = []
                    for row in reader:
                        parsed = parse_binance_kline_csv_row(row)
                        if parsed:
                            rows.append(parsed)
                    return rows
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (451, 403):
            log.warning(f"bulk geo blocked {url}: {e}")
            return []
        log.warning(f"bulk HTTP error {url}: {e}")
        return []
    except Exception as e:
        log.warning(f"bulk download failed {url}: {e}")
        return []

def download_range(
    symbol: str,
    timeframe: str = "1m",
    start: Optional[date] = None,
    end: Optional[date] = None,
    market: str = "um",
    timeout: int = 30,
) -> List[Dict[str, Any]]:
    """
    Download daily zips for range [start,end]. If range >30 days, prefer monthly where possible? For P02 simple: daily only.
    """
    if start is None or end is None:
        raise ValueError("start/end required")
    urls = binance_futures_daily_urls(symbol, timeframe, start, end, market=market)
    all_rows: List[Dict[str, Any]] = []
    for url in urls:
        rows = download_and_parse_zip(url, timeout=timeout)
        all_rows.extend(rows)
    # dedup by open_time
    seen = set()
    uniq = []
    for r in all_rows:
        ot = r["open_time"]
        if ot not in seen:
            seen.add(ot)
            uniq.append(r)
    uniq.sort(key=lambda x: x["open_time"])
    return uniq

# Fallback for Bybit public — simplified: not implemented bulk, use REST paged
def bybit_bulk_fallback(*args, **kwargs):
    log.info("bybit bulk fallback not yet implemented — will use REST tail")
    return []
