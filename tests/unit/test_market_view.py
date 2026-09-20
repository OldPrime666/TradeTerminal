from datetime import datetime, timezone, timedelta
import pandas as pd
from decimal import Decimal
from gcis.market.view import MarketView

def test_no_lookahead():
    base = datetime(2024,1,1, tzinfo=timezone.utc)
    rows=[
        {"open_time":base, "close_time":base+timedelta(minutes=15), "open":Decimal("100"),"high":Decimal("105"),"low":Decimal("99"),"close":Decimal("102"),"volume":Decimal("1000")},
        {"open_time":base+timedelta(minutes=15), "close_time":base+timedelta(minutes=30), "open":Decimal("102"),"high":Decimal("107"),"low":Decimal("101"),"close":Decimal("106"),"volume":Decimal("1000")},
        {"open_time":base+timedelta(minutes=30), "close_time":base+timedelta(minutes=45), "open":Decimal("106"),"high":Decimal("108"),"low":Decimal("104"),"close":Decimal("105"),"volume":Decimal("1000")},
    ]
    df=pd.DataFrame(rows)
    as_of = base+timedelta(minutes=30)  # after second bar closes, before third
    view = MarketView(as_of=as_of, candles={"BTCUSDT":{"15m":df}}, quotes={})
    got = view.get_closed_candles("BTCUSDT","15m")
    assert len(got)==2
    # future candle not visible
    assert got["close_time"].max() <= as_of

def test_quality_state():
    now=datetime.now(timezone.utc)
    view = MarketView(as_of=now, candles={}, quotes={"BTCUSDT":{"updated_at": now, "price": 50000}})
    assert view.quality_state("BTCUSDT")== "HEALTHY"
    # stale
    old = now - timedelta(seconds=10)
    view2 = MarketView(as_of=now, candles={}, quotes={"BTCUSDT":{"updated_at": old, "price":5000}})
    assert view2.quality_state("BTCUSDT")== "DEGRADED"
