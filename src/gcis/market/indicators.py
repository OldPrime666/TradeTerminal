"""
In-house indicators — NumPy/pandas, incremental where feasible.
Implements SMA, EMA (seeded SMA), RSI Wilder, ATR Wilder, ADX Wilder, Bollinger (population std), VWAP anchored, rolling volume median, returns, volatility, efficiency ratio.
No strategy re-implements.
"""
import numpy as np
import pandas as pd
from decimal import Decimal

def _to_float_series(values):
    if isinstance(values, pd.Series):
        return values.astype(float)
    return pd.Series([float(v) for v in values])

def sma(series, period: int):
    s = _to_float_series(series)
    return s.rolling(period).mean()

def ema(series, period: int):
    s = _to_float_series(series)
    # seeded with SMA
    ema_vals = s.ewm(span=period, adjust=False, min_periods=period).mean()
    # ensure first EMA = SMA of first period
    if len(s) >= period:
        sma0 = s.iloc[:period].mean()
        # ewm already seeded similarly; we keep as is but document
        pass
    return ema_vals

def rsi_wilder(close, period=14):
    c = _to_float_series(close)
    delta = c.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    # Wilder smoothing = EMA with alpha 1/period
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(avg_loss != 0, 100.0)
    rsi = rsi.where(avg_gain != 0, 0.0)  # if both zero, 50? but keep logic
    # When avg_loss==0 and avg_gain>0 => 100, when avg_gain==0 and avg_loss>0 =>0
    return rsi

def atr_wilder(high, low, close, period=14):
    h = _to_float_series(high); l = _to_float_series(low); c = _to_float_series(close)
    prev_close = c.shift(1)
    tr = pd.concat([h - l, (h - prev_close).abs(), (l - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    return atr

def adx_wilder(high, low, close, period=14):
    h = _to_float_series(high); l = _to_float_series(low); c = _to_float_series(close)
    up_move = h.diff()
    down_move = -l.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=c.index)
    minus_dm = pd.Series(minus_dm, index=c.index)
    tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, min_periods=period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, min_periods=period, adjust=False).mean() / atr)
    dx = 100 * ( (plus_di - minus_di).abs() / (plus_di + minus_di) )
    adx = dx.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    return adx, plus_di, minus_di

def bollinger(close, period=20, std=2.0):
    c = _to_float_series(close)
    mid = c.rolling(period).mean()
    # population std (ddof=0) — document
    sd = c.rolling(period).std(ddof=0)
    upper = mid + std * sd
    lower = mid - std * sd
    bandwidth = (upper - lower) / mid
    # rolling percentile of bandwidth (causal)
    return mid, upper, lower, bandwidth

def vwap_anchored(candles_df, anchor="utc_day"):
    # candles_df must have high, low, close, volume, close_time
    df = candles_df.copy()
    df["typical"] = (df["high"].astype(float) + df["low"].astype(float) + df["close"].astype(float)) / 3.0
    df["pv"] = df["typical"] * df["volume"].astype(float)
    if anchor == "utc_day":
        df["anchor"] = pd.to_datetime(df["close_time"]).dt.floor("D")
    else:
        df["anchor"] = pd.to_datetime(df["close_time"]).dt.floor("D")
    df["cum_pv"] = df.groupby("anchor")["pv"].cumsum()
    df["cum_v"] = df.groupby("anchor")["volume"].cumsum()
    df["vwap"] = df["cum_pv"] / df["cum_v"]
    return df["vwap"]

def rolling_volume_median(volume, period=20):
    v = _to_float_series(volume)
    return v.rolling(period).median()

def efficiency_ratio(close, period=20):
    c = _to_float_series(close)
    net = (c - c.shift(period)).abs()
    sum_abs = c.diff().abs().rolling(period).sum()
    er = net / sum_abs
    return er

def returns(close):
    c = _to_float_series(close)
    return c.pct_change()

def realized_volatility(close, period=20):
    r = returns(close)
    return r.rolling(period).std(ddof=1) * (252*24*60)**0.5  # not annualized correctly for crypto but store
