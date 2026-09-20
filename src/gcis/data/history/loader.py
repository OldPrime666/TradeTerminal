from pathlib import Path
from datetime import datetime, timezone
import httpx

def download_history(symbols: list, timeframe: str = "1m"):
    print(f"[history] Requested {symbols} {timeframe} — checking environment")
    # Try REST klines tail if bulk not available
    from gcis.core.config import get_config
    from gcis.data.exchange.binance import BinanceAdapter
    cfg = get_config()
    rest_base = cfg.get("exchange",{}).get("binance_rest_base","https://data-api.binance.vision")
    adapter = BinanceAdapter(rest_base=rest_base)
    try:
        # fetch recent 100 klines for each symbol as demo
        for sym in symbols:
            try:
                data = adapter.klines(sym, timeframe, limit=10)
                print(f"[history] {sym} got {len(data)} klines via REST (demo)")
                # would persist to var/archive Parquet etc
            except Exception as e:
                print(f"[history] {sym} REST failed (NO DATA expected in sandbox): {e}")
        print("[history] Bulk download from data.binance.vision not attempted in sandbox (would need zip handling, ms/µs normalize, Parquet). Marked UNVERIFIED_ENV for full loader.")
    finally:
        adapter.close()
