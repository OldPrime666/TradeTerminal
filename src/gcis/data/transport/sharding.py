"""
Sharding logic per ARC-20, DAT-04: ≤180 streams/conn, groups klines_1m / all_market / focus_set
"""
from typing import List, Dict, Any
import math

def shard_streams(streams: List[str], max_per_conn: int = 180) -> List[List[str]]:
    """Split streams into shards of max_per_conn each."""
    if not streams:
        return []
    shards: List[List[str]] = []
    for i in range(0, len(streams), max_per_conn):
        shards.append(streams[i:i+max_per_conn])
    return shards

def build_klines_streams(symbols: List[str], interval: str = "1m") -> List[str]:
    """Per-symbol kline stream for Binance futures: <symbol>@kline_1m (lowercase)"""
    return [f"{s.lower()}@kline_{interval}" for s in symbols]

def build_all_market_streams(symbols: List[str]) -> List[str]:
    """
    all_market group: shared streams for futures
    For Binance UM futures, includes per-symbol bookTicker and per-symbol markPrice? 
    Simplified: bookTicker per symbol + aggregate forceOrder stream
    """
    streams: List[str] = []
    for s in symbols:
        streams.append(f"{s.lower()}@bookTicker")
        # premiumIndex / markPrice stream (Binance futures: <symbol>@markPrice)
        streams.append(f"{s.lower()}@markPrice")
    # global liquidation stream (Binance: !forceOrder@arr)
    streams.append("!forceOrder@arr")
    return streams

def build_focus_streams(symbols: List[str]) -> List[str]:
    """focus_set: depth + aggTrade for in-risk positions only (P03: small set)"""
    streams = []
    for s in symbols:
        streams.append(f"{s.lower()}@depth@0ms")  # simplified
        streams.append(f"{s.lower()}@aggTrade")
    return streams

def plan_shards(
    symbols: List[str],
    focus_symbols: List[str] | None = None,
    max_per_conn: int = 180,
) -> Dict[str, List[List[str]]]:
    """
    Returns dict group -> list of shards (each shard is list of streams)
    For N tradable contracts, klines_1m shards = ceil(N/180)
    """
    focus_symbols = focus_symbols or []
    klines = build_klines_streams(symbols, "1m")
    all_market = build_all_market_streams(symbols)
    focus = build_focus_streams(focus_symbols)

    return {
        "klines_1m": shard_streams(klines, max_per_conn),
        "all_market": shard_streams(all_market, max_per_conn),
        "focus_set": shard_streams(focus, max_per_conn),
    }

def shard_summary(plan: Dict[str, List[List[str]]]) -> Dict[str, Any]:
    """Human summary for health / metrics"""
    out: Dict[str, Any] = {}
    for group, shards in plan.items():
        total_streams = sum(len(s) for s in shards)
        out[group] = {"shards": len(shards), "streams": total_streams}
    return out
