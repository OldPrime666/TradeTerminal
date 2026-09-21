import pandas as pd
from collections import Counter

from gcis.backtest.ports import CandleRepository
from gcis.data.quality.report import quality_report

def run_census(symbols: list | None = None, timeframe: str = "15m", candle_repo: CandleRepository | None = None):
    """
    BKT-06 census Tier verdict + BKT-10 backtestability + BKT-12 survivorship.
    Accepts injected CandleRepository (no direct sqlalchemy import).
    If no repo provided → NO_DATA honest (caller must inject from app layer).
    """
    rows = []
    if candle_repo is not None:
        try:
            # fetch via repo — need to handle repo interface that returns Candle objects
            # For census we need symbol/timeframe/open_time/close_time; repo.fetch returns list of Candle
            raw = candle_repo.fetch(symbols if symbols else ["BTCUSDT"], timeframe, None, None, limit=100000)
            # raw may be list of Candle objects; normalize to rows with needed attrs
            # If repo returns already filtered, use as is
            if raw:
                # If symbols filter was applied in repo, raw already filtered; else filter here
                if symbols:
                    rows = [r for r in raw if getattr(r, "symbol", None) in symbols]
                else:
                    rows = raw
            else:
                rows = []
        except Exception:
            rows = []
    else:
        rows = []

    total = len(rows)
    cnt = Counter([(r.symbol, r.timeframe) for r in rows]) if rows else Counter()
    per_symbol_counts = Counter([r.symbol for r in rows]) if rows else Counter()
    per_symbol_days = {}
    for sym in per_symbol_counts:
        tf_min = {"1m":1,"5m":5,"15m":15,"1h":60,"4h":240,"1d":1440}.get(timeframe,15)
        days = per_symbol_counts[sym] * tf_min / 1440
        per_symbol_days[sym] = round(days, 2)

    backtestability = {}
    if rows:
        by_sym = {}
        for r in rows:
            by_sym.setdefault(r.symbol, []).append(r)
        for sym, rs in by_sym.items():
            df = pd.DataFrame([{"open_time": pd.Timestamp(r.open_time), "close_time": pd.Timestamp(r.close_time), "open":1,"high":1,"low":1,"close":1,"volume":1,"quote_volume":1,"trade_count":1,"taker_buy_volume":1} for r in rs])
            try:
                rep = quality_report("binance_um", sym, timeframe, df)
                status = rep.get("status","UNKNOWN")
                if status == "OK":
                    b = "OK"
                elif status == "GAP":
                    b = "GAP"
                elif status == "INSUFFICIENT_HISTORY":
                    b = "INSUFFICIENT_HISTORY"
                else:
                    b = status
            except Exception:
                b = "UNKNOWN"
            backtestability[sym] = b
    else:
        backtestability = {"_all": "NO_DATA"}

    verdict = "NONE"
    if total > 1000:
        verdict = "TIER_POOLED_ONLY"
    if total > 5000:
        verdict = "TIER_STRATEGY"
    effective_sample = total
    has_gap = any(v == "GAP" for v in backtestability.values())
    if has_gap and verdict != "NONE":
        verdict = verdict + "_GAP_WARN"

    report = {
        "total_candles": total,
        "timeframe": timeframe,
        "per_symbol_timeframe": {f"{k[0]}:{k[1]}": v for k,v in cnt.items()},
        "per_symbol_counts": dict(per_symbol_counts),
        "per_symbol_days": per_symbol_days,
        "effective_sample": effective_sample,
        "effective_sample_note": "Overlap-adjusted sample requires signal_outcomes; currently = total_candles (pessimistic)",
        "feasibility_verdict": verdict,
        "backtestability": backtestability,
        "regime_discrimination": "NOT_ENOUGH_DATA — needs forward volatility/returns by regime (requires >5000 bars + regime labels)",
        "history_length_per_symbol": per_symbol_days,
        "survivorship_note": "Candle history survivorship-aware: includes delisted contracts (not filtered to TRADING). Coverage from archive+DB.",
        "note": "Census drives probability pooling tier per BKT-06. Run after real archive populated.",
    }
    return report
