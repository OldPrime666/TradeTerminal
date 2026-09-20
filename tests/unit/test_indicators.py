import pandas as pd
from gcis.market.indicators import sma, ema, rsi_wilder, atr_wilder, bollinger, efficiency_ratio

def test_sma():
    s = pd.Series([1,2,3,4,5])
    res = sma(s, 3)
    assert abs(res.iloc[2] - 2.0) < 1e-9
    assert abs(res.iloc[4] - 4.0) < 1e-9

def test_ema_seeded():
    s = pd.Series([1,2,3,4,5]*10)
    e = ema(s, 3)
    assert not e.isna().all()
    # causality: appending future bars never changes past outputs
    s2 = pd.Series([1,2,3,4,5]*10 + [100,100])
    e2 = ema(s2, 3)
    assert abs(e.iloc[5] - e2.iloc[5]) < 1e-9

def test_rsi_wilder():
    c = pd.Series([44,44.34,44.09,43.61,44.33,44.83]*5)
    r = rsi_wilder(c,14)
    assert r.iloc[-1] >=0 and r.iloc[-1] <=100

def test_atr_wilder():
    h = pd.Series([10,11,12]*10, dtype=float)
    l = pd.Series([9,10,11]*10, dtype=float)
    c = pd.Series([9.5,10.5,11.5]*10, dtype=float)
    atr = atr_wilder(h,l,c,14)
    assert atr.iloc[-1] >0

def test_bollinger():
    c = pd.Series([10]*30, dtype=float)
    mid, upper, lower, bw = bollinger(c,20,2.0)
    assert abs(mid.iloc[-1]-10) < 1e-9
    assert bw.iloc[-1] < 1e-9

def test_efficiency_ratio():
    c = pd.Series(range(30), dtype=float)
    er = efficiency_ratio(c,20)
    assert er.iloc[-1] >0
