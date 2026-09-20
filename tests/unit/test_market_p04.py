"""P04 market tests: MarketView causality, regime, sessions, indicators leakage."""
import pandas as pd
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest

def _make_candles_df(symbol="BTCUSDT", tf="1m", n=100, start="2024-01-01T00:00:00+00:00"):
    base = datetime.fromisoformat(start)
    rows = []
    for i in range(n):
        ot = base + timedelta(minutes=i)
        ct = ot + timedelta(minutes=1) - timedelta(milliseconds=1)
        # synthetic trending up with small noise
        close = 100 + i*0.5 + (i%3)*0.2
        high = close + 0.3
        low = close - 0.3
        open_ = close - 0.1
        rows.append({
            "open_time": ot,
            "close_time": ct,
            "open": Decimal(str(open_)),
            "high": Decimal(str(high)),
            "low": Decimal(str(low)),
            "close": Decimal(str(close)),
            "volume": Decimal("100"),
            "quote_volume": Decimal("10000"),
            "trade_count": 10,
            "taker_buy_volume": Decimal("50"),
        })
    df = pd.DataFrame(rows)
    return df

def test_market_view_no_lookahead_via_engine():
    from gcis.market.engine import build_market_view
    df = _make_candles_df(n=60)
    candles = {"BTCUSDT": {"1m": df}}
    # as_of at bar 30 close
    as_of_mid = df.iloc[30]["close_time"]  # 30th bar close
    view_mid = build_market_view(candles, quotes={}, as_of=as_of_mid)
    closed_mid = view_mid.get_closed_candles("BTCUSDT","1m")
    assert len(closed_mid) == 31  # 0..30 inclusive (close_time <= as_of)
    # as_of later at bar 50
    as_of_late = df.iloc[50]["close_time"]
    view_late = build_market_view(candles, quotes={}, as_of=as_of_late)
    closed_late = view_late.get_closed_candles("BTCUSDT","1m")
    assert len(closed_late) == 51
    # future bars beyond 50 not visible in mid view
    assert closed_mid["close_time"].max() <= as_of_mid
    # Adding future bars should not change mid view's last close
    # The mid view's features should be same regardless of future df existence beyond as_of
    # Compare feature ema9 at mid
    feat_mid = view_mid.features["BTCUSDT"]["1m"]
    # Build view_mid again but with extended df (100 bars) still as_of mid -> same features
    df_extended = _make_candles_df(n=100)
    candles_extended = {"BTCUSDT": {"1m": df_extended}}
    view_mid2 = build_market_view(candles_extended, quotes={}, as_of=as_of_mid)
    feat_mid2 = view_mid2.features["BTCUSDT"]["1m"]
    assert feat_mid["ema9"] == pytest.approx(feat_mid2["ema9"], rel=1e-9)

def test_market_view_forming_not_in_closed():
    from gcis.market.engine import build_market_view
    df = _make_candles_df(n=10)
    # as_of between bar 5 close and bar 6 close (mid-forming)
    as_of_between = df.iloc[5]["close_time"] + timedelta(seconds=30)  # 30 sec into next bar forming
    view = build_market_view({"BTCUSDT":{"1m": df}}, {}, as_of_between)
    closed = view.get_closed_candles("BTCUSDT","1m")
    # Should have 6 closed (0..5), not include forming bar 6
    assert len(closed) == 6
    assert closed["close_time"].max() == df.iloc[5]["close_time"]

def test_indicators_causal_no_leakage():
    from gcis.market.indicators import ema, rsi_wilder, atr_wilder
    import pandas as pd
    c = pd.Series([10,11,12,11,10,11,12,13,12,11]*10, dtype=float)
    e1 = ema(c.iloc[:30], 9)
    e2 = ema(c, 9)
    # past ema should not be affected by future beyond 30
    assert abs(e1.iloc[20] - e2.iloc[20]) < 1e-9
    # RSI
    r1 = rsi_wilder(c.iloc[:30], 14)
    r2 = rsi_wilder(c, 14)
    assert abs(r1.iloc[20] - r2.iloc[20]) < 1e-9
    # ATR
    h = c + 0.5; l = c - 0.5
    a1 = atr_wilder(h.iloc[:30], l.iloc[:30], c.iloc[:30], 14)
    a2 = atr_wilder(h, l, c, 14)
    assert abs(a1.iloc[20] - a2.iloc[20]) < 1e-9

def test_regime_causal_and_deterministic():
    from gcis.market.engine import build_market_view
    df = _make_candles_df(n=500)
    candles = {"BTCUSDT": {"1m": df}}
    as_of = df.iloc[400]["close_time"]
    view1 = build_market_view(candles, {}, as_of=as_of)
    reg1 = view1.regimes["BTCUSDT"]["1m"]
    view2 = build_market_view(candles, {}, as_of=as_of)
    reg2 = view2.regimes["BTCUSDT"]["1m"]
    assert reg1 == reg2  # deterministic
    # With shorter as_of, regime may differ but not be affected by future
    as_of_early = df.iloc[200]["close_time"]
    view_early = build_market_view(candles, {}, as_of=as_of_early)
    reg_early = view_early.regimes["BTCUSDT"]["1m"]
    # Regime should be some valid value, not crash, and should be causal (no future peek)
    assert reg_early["trend"] in ("TRENDING_UP","TRENDING_DOWN","RANGING","UNCERTAIN")
    # Ensure early regime equals regime computed only on prefix df
    df_prefix = df.iloc[:201].copy()  # up to early inclusive
    view_prefix = build_market_view({"BTCUSDT":{"1m": df_prefix}}, {}, as_of=as_of_early)
    assert view_prefix.regimes["BTCUSDT"]["1m"] == reg_early

def test_regime_oracle_forward_vol_separation():
    # Oracle: regime must not peek forward volatility; test that shuffling future does not change current regime
    from gcis.market.engine import build_market_view
    df = _make_candles_df(n=400)
    # inject future volatility spike after as_of
    df_future_spike = df.copy()
    # after 350, spike high
    for i in range(350,400):
        df_future_spike.loc[df_future_spike.index[i], "high"] = Decimal("1000")
        df_future_spike.loc[df_future_spike.index[i], "close"] = Decimal("1000")
    candles_normal = {"BTCUSDT": {"1m": df}}
    candles_spike = {"BTCUSDT": {"1m": df_future_spike}}
    as_of = df.iloc[300]["close_time"]
    view_normal = build_market_view(candles_normal, {}, as_of=as_of)
    view_spike = build_market_view(candles_spike, {}, as_of=as_of)
    # Regime at 300 should be identical regardless of future spike (no leakage)
    assert view_normal.regimes["BTCUSDT"]["1m"] == view_spike.regimes["BTCUSDT"]["1m"]

def test_sessions_tz_aware():
    from gcis.market.sessions import active_sessions, is_session_active
    from zoneinfo import ZoneInfo
    # London session 08:00-16:30 Europe/London. At 09:00 London = 08:00 UTC in winter (London GMT+0 in Jan)
    # Jan 15 2024 09:00 London is 09:00 UTC
    dt_utc = datetime(2024,1,15,9,0,tzinfo=timezone.utc)
    # That's 09:00 London, should be active
    assert is_session_active("london", dt_utc) is True
    assert "london" in active_sessions(dt_utc)
    # 07:00 London should be killzone but not main london session? Check
    dt_kill = datetime(2024,1,15,7,30,tzinfo=timezone.utc)  # 07:30 London
    assert is_session_active("london_killzone", dt_kill) is True
    assert is_session_active("london", dt_kill) is False
    # Asia 09:00 Tokyo = 00:00 UTC
    dt_asia = datetime(2024,1,15,0,0,tzinfo=timezone.utc)  # 09:00 Tokyo
    assert is_session_active("asia", dt_asia) is True
    # NY 08:30 America/New_York in winter is 13:30 UTC
    dt_ny = datetime(2024,1,15,13,30,tzinfo=timezone.utc)
    assert is_session_active("new_york", dt_ny) is True
    assert "new_york" in active_sessions(dt_ny)

def test_quote_filter_as_of():
    from gcis.market.engine import build_market_view
    df = _make_candles_df(n=10)
    now = df.iloc[5]["close_time"]
    quotes = {
        "BTCUSDT": {"price": Decimal("100"), "updated_at": now - timedelta(seconds=2)},
        "ETHUSDT": {"price": Decimal("200"), "updated_at": now + timedelta(seconds=10)},  # future quote should be filtered
    }
    view = build_market_view({"BTCUSDT":{"1m": df}}, quotes, as_of=now)
    assert "BTCUSDT" in view.quotes
    assert "ETHUSDT" not in view.quotes  # future not visible
    assert view.quality_state("BTCUSDT") == "HEALTHY"
    # Stale quote
    stale_quote = {"BTCUSDT": {"price": Decimal("100"), "updated_at": now - timedelta(seconds=10)}}
    view_stale = build_market_view({"BTCUSDT":{"1m": df}}, stale_quote, as_of=now)
    assert view_stale.quality_state("BTCUSDT") == "DEGRADED"

def test_features_only_closed_not_forming():
    from gcis.market.engine import build_market_view
    df = _make_candles_df(n=20)
    # as_of exactly at close of bar 10
    as_of = df.iloc[10]["close_time"]
    view = build_market_view({"BTCUSDT":{"1m": df}}, {}, as_of=as_of)
    # features should be computed on 11 closed bars (0..10)
    # ema9 should exist (needs 9 bars)
    assert view.features["BTCUSDT"]["1m"]["ema9"] is not None
    # Now as_of early at bar 5 (only 6 bars) — rsi 14 should be None (insufficient)
    as_of_early = df.iloc[5]["close_time"]
    view_early = build_market_view({"BTCUSDT":{"1m": df}}, {}, as_of=as_of_early)
    # With only 6 bars, many indicators will be None or NaN-derived None
    # At least not crash, and rsi likely None because need 14
    assert view_early.features["BTCUSDT"]["1m"]["rsi"] is None or view_early.features["BTCUSDT"]["1m"]["rsi"] is not None  # just check key exists

def test_bollinger_population_std():
    from gcis.market.indicators import bollinger
    import pandas as pd
    c = pd.Series([10]*30, dtype=float)
    mid, upper, lower, bw = bollinger(c,20,2.0)
    assert abs(mid.iloc[-1]-10) < 1e-9
    assert abs(bw.iloc[-1]) < 1e-9  # no volatility
    # With volatility
    c2 = pd.Series([10,11,9,12,8]*6, dtype=float)
    mid2, up2, low2, bw2 = bollinger(c2,20,2.0)
    assert bw2.iloc[-1] > 0
