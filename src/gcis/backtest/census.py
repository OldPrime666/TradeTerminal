import pandas as pd
from gcis.persistence.db import get_session
from gcis.persistence.models import Candle

def run_census():
    db = get_session()
    try:
        # count per symbol/timeframe
        rows = db.query(Candle.symbol, Candle.timeframe).all()
        from collections import Counter
        cnt = Counter([(r.symbol, r.timeframe) for r in rows])
        total = len(rows)
        # also try to compute regime discrimination placeholder
        # For now, emit feasibility verdict
        # TIER logic from Part12 census_thresholds
        # We have no signal outcomes yet -> NONE or TIER_POOLED_ONLY if we had data
        verdict = "NONE"
        if total > 1000:
            verdict = "TIER_POOLED_ONLY"
        if total > 5000:
            verdict = "TIER_STRATEGY"
        report = {
            "total_candles": total,
            "per_symbol_timeframe": {f"{k[0]}:{k[1]}": v for k,v in cnt.items()},
            "effective_sample_note": "Overlap-adjusted sample requires signal_outcomes; currently 0",
            "feasibility_verdict": verdict,
            "regime_discrimination": "NOT_ENOUGH_DATA — needs forward volatility/returns by regime",
            "history_length_per_symbol": {k[0]: v for k,v in cnt.items()},
            "note": "Census drives probability pooling tier per BKT-06. Run after real archive populated.",
        }
        return report
    finally:
        db.close()
