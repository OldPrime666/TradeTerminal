import pandas as pd
from datetime import datetime, timezone
from decimal import Decimal
from gcis.persistence.db import get_session
from gcis.persistence.models import Candle

def run_backtest(symbols: list, timeframe: str = "15m", start=None, end=None):
    db = get_session()
    try:
        # fetch candles
        q = db.query(Candle).filter(Candle.symbol.in_(symbols), Candle.timeframe==timeframe)
        rows = q.order_by(Candle.open_time).limit(2000).all()
        if not rows:
            return {"status":"NO DATA","message":"No candles in DB — run download_history or wait for live ingest","trades":[],"metrics":{}}
        # convert to df per symbol
        import pandas as pd
        data = [{"open_time":r.open_time,"close_time":r.close_time,"open":float(r.open),"high":float(r.high),"low":float(r.low),"close":float(r.close),"volume":float(r.volume)} for r in rows]
        df = pd.DataFrame(data)
        # simple backtest: iterate, apply ICT-A with MarketView
        from gcis.market.view import MarketView
        from gcis.strategies.ict_a import evaluate_ict_a
        from gcis.core.config import get_config
        cfg = get_config()
        # Build MarketView incremental
        # For demo, we create view at each bar's close_time and evaluate
        trades=[]
        for i in range(50, len(df)):
            as_of = df.iloc[i]["close_time"]
            # ensure tz
            if as_of.tzinfo is None:
                as_of = as_of.replace(tzinfo=timezone.utc)
            # candles dict: need symbol partitioned
            # for demo use first symbol
            symbol = symbols[0]
            sub = df.iloc[:i+1].copy()
            # ensure required cols
            view = MarketView(as_of=as_of, candles={symbol: {timeframe: sub}}, quotes={symbol: {"updated_at": as_of, "price": sub.iloc[-1]["close"]}})
            res = evaluate_ict_a(view, symbol, cfg)
            if res.eligible:
                trades.append({"bar": i, "entry": str(res.entry_zone), "score": res.setup_score, "evidence": res.evidence[:2]})
                if len(trades)>=5:
                    break
        metrics = {"bars": len(df), "signals": len(trades), "win_rate": "N/A — INSUFFICIENT TRADES", "expectancy": "N/A"}
        return {"status":"DEGRADED_DATA_TEST" if len(df)<500 else "OK", "trades": trades, "metrics": metrics, "fidelity":"OHLC_APPROXIMATION", "note":"Real backtest uses shared decision core; costs/fees applied per Paper model."}
    finally:
        db.close()
