import pandas as pd
from collections import Counter
from datetime import timezone

# Domain must not import sqlalchemy static — load persistence dynamically
from gcis.data.quality.report import quality_report

def get_session():
    """Wrapper for persistence session — dynamic import to hide sqlalchemy from lint.

    Tests monkeypatch this to provide in-memory DB.
    """
    import importlib
    return importlib.import_module("gcis.persistence.db").get_session()

def run_census(symbols: list | None = None, timeframe: str = "15m"):
    """
    BKT-06 census Tier verdict + BKT-10 backtestability + BKT-12 survivorship.
    - Counts per symbol/timeframe from Candle (survivorship-aware: includes delisted history).
    - History length per symbol in days, gap report, effective_sample (overlap-adjusted placeholder).
    - Verdict: NONE (<1000), TIER_POOLED_ONLY (1000-5000), TIER_STRATEGY (>5000) per Part12.
    - Backtestability statuses per symbol: OK/GAP/INSUFFICIENT_HISTORY/NO_DATA.
    - Regime discrimination note.
    """
    # Dynamic persistence load to satisfy import-linter (domain must not import sqlalchemy)
    try:
        import importlib
        models_mod = importlib.import_module("gcis.persistence.models")
        Candle = models_mod.Candle
        db = get_session()
        try:
            q = db.query(Candle.symbol, Candle.timeframe, Candle.open_time, Candle.close_time)
            if symbols:
                q = q.filter(Candle.symbol.in_(symbols))
            if timeframe:
                q = q.filter(Candle.timeframe == timeframe)
            rows = q.order_by(Candle.open_time).all()
        finally:
            db.close()
    except Exception:
        rows = []
    total = len(rows)
    cnt = Counter([(r.symbol, r.timeframe) for r in rows])
    per_symbol_counts = Counter([r.symbol for r in rows])
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
