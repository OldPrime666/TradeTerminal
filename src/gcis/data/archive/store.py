"""
Archive store (ARC-07, DAT-10) — Parquet+zstd, partition by venue/symbol/timeframe, idempotent, resumable.
Handles disk budget 200GB, checksum via SHA256, µs normalized timestamps.
"""
from pathlib import Path
import hashlib
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timezone
from decimal import Decimal
import logging

log = logging.getLogger(__name__)

ARCHIVE_ROOT = Path("var/archive")

def ensure_root() -> Path:
    ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)
    return ARCHIVE_ROOT

def archive_path(venue: str, symbol: str, timeframe: str, date_str: str) -> Path:
    """
    date_str like 2024-01-01 for daily, or 2024-01 for monthly.
    Returns path: var/archive/<venue>/<symbol>/<timeframe>/<date_str>.parquet
    """
    return ARCHIVE_ROOT / venue / symbol / timeframe / f"{date_str}.parquet"

def write_parquet(df: pd.DataFrame, path: Path) -> str:
    """
    Write DataFrame to Parquet with zstd. Returns sha256 hex.
    DataFrame must have columns: open_time (datetime64[ns,UTC] or µs int), close_time etc.
    Idempotent: if path exists with same rows, skip write? Caller handles check.
    """
    ensure_root()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Convert to pyarrow table with compression
    table = pa.Table.from_pandas(df, preserve_index=False)
    # write with zstd
    pq.write_table(table, str(path), compression="zstd", use_dictionary=True)
    # compute sha256 of file
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    log.info(f"archive: wrote {path} rows={len(df)} sha={sha[:12]}")
    return sha

def read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    table = pq.read_table(str(path))
    return table.to_pandas()

def list_segments(venue: str, symbol: str, timeframe: str) -> list[Path]:
    root = ARCHIVE_ROOT / venue / symbol / timeframe
    if not root.exists():
        return []
    return sorted(root.glob("*.parquet"))

def disk_free_gb() -> float:
    import shutil
    return shutil.disk_usage(str(ARCHIVE_ROOT)).free / (1024 ** 3)

def check_disk_budget(min_free_gb: int = 10, hard_min_gb: int = 2) -> str:
    """
    Returns status: OK, WARN (below 10), BLOCK (below 2)
    """
    free = disk_free_gb()
    if free < hard_min_gb:
        return f"BLOCK:{free:.1f}GB"
    if free < min_free_gb:
        return f"WARN:{free:.1f}GB"
    return f"OK:{free:.1f}GB"

def normalize_timestamp_to_us(ts: int) -> int:
    """Binance historical CSVs: before 2025-01-01 futures still ms (13 digits), after maybe µs? Normalize to µs."""
    if ts < 1_000_000_000_000:  # seconds
        return int(ts * 1_000_000)
    elif ts < 1_000_000_000_000_000:  # ms
        return int(ts * 1000)
    else:
        return int(ts)

def df_from_bulk_rows(rows: list[dict], venue: str, symbol: str, timeframe: str) -> pd.DataFrame:
    """
    rows: list of dicts with keys open_time (us), open, high, low, close, volume, close_time, quote_volume, trades etc.
    Returns DataFrame with proper dtypes (Decimal stored as string? but use float for parquet then Decimal on read)
    Keep Decimal as string to preserve precision? For now store as float for speed; persistence restores Decimal.
    """
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # Ensure datetime columns as UTC
    for col in ("open_time", "close_time"):
        if col in df.columns:
            # convert us int to datetime
            df[col] = pd.to_datetime(df[col], unit="us", utc=True)
    # Sort by open_time
    if "open_time" in df.columns:
        df = df.sort_values("open_time")
    return df

def derive_timeframe(df_1m: pd.DataFrame, target: str) -> pd.DataFrame:
    """
    Derive higher timeframe from 1m base (ARC-20a). Only derive, never store extra raw beyond 1m.
    target: 5m,15m,1h,4h,1d
    Checks aggregation vs venue kline? For P02 we just resample by open_time.
    """
    if df_1m.empty:
        return df_1m
    # Ensure sorted
    df = df_1m.copy()
    df = df.sort_values("open_time")
    df.set_index("open_time", inplace=True)
    # mapping
    tf_map = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "60min", "4h": "240min", "1d": "1440min"}
    rule = tf_map.get(target)
    if not rule:
        raise ValueError(f"unsupported timeframe {target}")
    # Resample: OHLC, volume sum, etc.
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "quote_volume": "sum",
        "trade_count": "sum",
        "taker_buy_volume": "sum",
    }
    # Filter available columns
    agg = {k: v for k, v in agg.items() if k in df.columns}
    res = df.resample(rule, label="left", closed="left").agg(agg)
    # Need close_time = open_time + tf
    # Derive
    res = res.dropna(subset=["open", "close"])
    res["close_time"] = res.index + pd.to_timedelta(rule)
    # Reset index to open_time column
    res = res.reset_index()
    # keep order
    return res

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
