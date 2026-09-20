import pandas as pd
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from gcis.ict.swings import detect_swings
from gcis.market.indicators import atr_wilder

def make_df(n=50):
    base = datetime(2024,1,1, tzinfo=timezone.utc)
    rows=[]
    for i in range(n):
        # create swing highs every 10 bars
        if i%10==5:
            high=110
            low=90
        else:
            high=105
            low=95
        open_=100
        close=101 if i%2==0 else 99
        rows.append({"open_time": base+timedelta(minutes=i*15), "close_time": base+timedelta(minutes=(i+1)*15), "open": Decimal("100"),"high": Decimal(str(high)),"low": Decimal(str(low)),"close": Decimal(str(close)),"volume": Decimal("1000")})
    df=pd.DataFrame(rows)
    return df

def test_swings_no_repaint():
    df = make_df(100)
    atr = atr_wilder(df["high"].astype(float), df["low"].astype(float), df["close"].astype(float),14)
    swings_full = detect_swings(df, "BTCUSDT","15m", L=3,R=3, atr_series=atr)
    # prefix test: first 50 bars
    df_prefix = df.iloc[:50].copy()
    atr_p = atr[:50]
    swings_prefix = detect_swings(df_prefix, "BTCUSDT","15m", L=3,R=3, atr_series=atr_p)
    # swings confirmed at p+R should be identical for bars <= 47
    # compare ids that are within prefix
    prefix_ids = set(s.swing_id for s in swings_prefix)
    full_ids_subset = set(s.swing_id for s in swings_full if "BTCUSDT-15m" in s.swing_id and int(s.swing_id.split("-")[-1]) < 50-3)
    # At least prefix swings should be subset of full
    assert prefix_ids.issubset(set(s.swing_id for s in swings_full))

def test_swings_golden():
    # hand-built case: swing high at bar 3
    base = datetime(2024,1,1,tzinfo=timezone.utc)
    rows=[
        {"open_time":base, "close_time":base+timedelta(minutes=15), "open":Decimal("10"),"high":Decimal("10"),"low":Decimal("9"),"close":Decimal("9.5"),"volume":Decimal("100")},
        {"open_time":base+timedelta(minutes=15), "close_time":base+timedelta(minutes=30), "open":Decimal("10"),"high":Decimal("11"),"low":Decimal("9"),"close":Decimal("10"),"volume":Decimal("100")},
        {"open_time":base+timedelta(minutes=30), "close_time":base+timedelta(minutes=45), "open":Decimal("10"),"high":Decimal("12"),"low":Decimal("9"),"close":Decimal("11"),"volume":Decimal("100")},
        {"open_time":base+timedelta(minutes=45), "close_time":base+timedelta(minutes=60), "open":Decimal("11"),"high":Decimal("13"),"low":Decimal("10"),"close":Decimal("12"),"volume":Decimal("100")}, # pivot 13
        {"open_time":base+timedelta(minutes=60), "close_time":base+timedelta(minutes=75), "open":Decimal("12"),"high":Decimal("12.5"),"low":Decimal("10"),"close":Decimal("11"),"volume":Decimal("100")},
        {"open_time":base+timedelta(minutes=75), "close_time":base+timedelta(minutes=90), "open":Decimal("11"),"high":Decimal("12"),"low":Decimal("10"),"close":Decimal("10.5"),"volume":Decimal("100")},
        {"open_time":base+timedelta(minutes=90), "close_time":base+timedelta(minutes=105), "open":Decimal("10.5"),"high":Decimal("11.5"),"low":Decimal("9.5"),"close":Decimal("10"),"volume":Decimal("100")},
    ]
    df=pd.DataFrame(rows)
    atr=atr_wilder(df["high"].astype(float), df["low"].astype(float), df["close"].astype(float),14)
    swings=detect_swings(df,"BTCUSDT","15m",L=3,R=3, atr_series=atr)
    # pivot at index 3 should be confirmed after 3 bars (index6) -> need at least 7 rows, we have 7, so swing high at p=3
    assert any(s.type=="HIGH" and "3" in s.swing_id for s in swings)
