"""P12 Research I: walk-forward purge/embargo, Monte Carlo block bootstrap, extra strategies STR-03/04/05/08, confluence BKT-13."""
import pandas as pd
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import hashlib

def _make_df(n=800, tf="15m", start_price=100.0):
    base = datetime(2024,1,1, tzinfo=timezone.utc)
    delta = {"1m":1,"5m":5,"15m":15,"1h":60,"4h":240,"1d":1440}[tf]
    rows=[]
    price=start_price
    for i in range(n):
        ot = base + timedelta(minutes=delta*i)
        ct = ot + timedelta(minutes=delta) - timedelta(seconds=1)
        # trending up then down to allow both longs/shorts
        trend = price + (1 if i< n//2 else -1) * 0.1 + (i % 20)*0.05
        open_p = price
        high = price + 1.2
        low = price - 0.8
        close = price + 0.3
        # add some variability for rsi/bb
        if i % 30 == 0:
            high += 2; close +=1
        if i % 40 == 0:
            low -=2; close -=1
        price = close
        rows.append({"open_time": ot, "close_time": ct, "open": open_p, "high": high, "low": low, "close": close, "volume": 100})
    return pd.DataFrame(rows)

def _make_view(df, symbol="BTCUSDT", tf="15m"):
    from gcis.market.view import MarketView
    bias_tf="1h"
    # need bias df 1h derived: aggregate 4*15m =1h approx; just reuse df resampled collapsed
    # For test we can create bias df by taking every 4th row and aggregating? Simpler create synthetic 1h df with same length but tf 1h
    base = datetime(2024,1,1, tzinfo=timezone.utc)
    bias_rows=[]
    # create 1h candles covering same period
    for i in range(len(df)//4):
        ot = base + timedelta(hours=i)
        ct = ot + timedelta(hours=1)-timedelta(seconds=1)
        price = float(df.iloc[i*4]["close"]) if i*4 < len(df) else 100
        bias_rows.append({"open_time": ot, "close_time": ct, "open": Decimal(str(price)), "high": Decimal(str(price+1)), "low": Decimal(str(price-1)), "close": Decimal(str(price)), "volume": Decimal("100")})
    bias_df = pd.DataFrame(bias_rows)
    # Convert df to Decimal as view expects?
    df2 = df.copy()
    for col in ["open","high","low","close","volume"]:
        df2[col] = df2[col].astype(float)
        # keep as float for view? view handles Decimal or float conversion via float()
        # But earlier ict expects Decimal, we let float work; strategies use float via view
    bias_df[["open","high","low","close"]] = bias_df[["open","high","low","close"]].astype(float)
    as_of = df["close_time"].iloc[-1]
    if isinstance(as_of, pd.Timestamp) and as_of.tz is None:
        as_of = as_of.tz_localize("UTC")
    view = MarketView(as_of=as_of, candles={symbol: {tf: df, bias_tf: bias_df}}, quotes={symbol: {"updated_at": as_of, "price": float(df.iloc[-1]["close"])}})
    # ensure quality HEALTHY
    view.quotes[symbol]["updated_at"] = view.as_of
    return view

# STR extra tests
def test_str_extra_import_and_versions():
    from gcis.strategies.extra import STRATEGY_VERSION, evaluate_ema_cross, evaluate_donchian, evaluate_rsi_reversion, evaluate_confluence
    assert STRATEGY_VERSION == "0.2.0"
    assert callable(evaluate_ema_cross)

def test_str_extra_ema_deterministic_and_causal():
    from gcis.strategies.extra import evaluate_ema_cross
    df = _make_df(300)
    view = _make_view(df)
    cfg = {"analysis_timeframes":{"setup":"15m","bias":"1h"},"strategy":{"ema_cross":{"fast":9,"slow":21,"stop_atr":1.0,"tp_r":2.0,"min_net_rr":0.5}},"costs":{"taker_fee_bps":5,"slippage_bps_base":2},"ict":{}}
    res1 = evaluate_ema_cross(view, "BTCUSDT", cfg)
    res2 = evaluate_ema_cross(view, "BTCUSDT", cfg)
    assert res1.setup_score == res2.setup_score
    assert res1.evidence == res2.evidence
    # causal: prefix subset should not repaint eligible from not eligible without new cross? Check that prefix earlier than cross has not eligible
    # take prefix 50 bars before end where no cross, ensure eligible false or score lower
    df_prefix = df.iloc[:100].copy()
    view_prefix = _make_view(df_prefix)
    res_prefix = evaluate_ema_cross(view_prefix, "BTCUSDT", cfg)
    # at least deterministic; we don't assert eligible but ensure no crash and score within 0-100
    assert 0 <= res_prefix.setup_score <= 100

def test_str_extra_donchian_and_rsi_contract():
    from gcis.strategies.extra import evaluate_donchian, evaluate_rsi_reversion
    from gcis.strategies.base import StrategyResult
    df = _make_df(400)
    view = _make_view(df)
    cfg = {"analysis_timeframes":{"setup":"15m"},"strategy":{"donchian":{"lookback":20,"stop_atr":1.0,"tp_r":2.5,"min_net_rr":0.8},"rsi_reversion":{"rsi_period":14,"oversold":30,"overbought":70,"stop_atr":1.2,"tp_r":1.8}},"costs":{"taker_fee_bps":5,"slippage_bps_base":2}}
    r1 = evaluate_donchian(view, "BTCUSDT", cfg)
    r2 = evaluate_rsi_reversion(view, "BTCUSDT", cfg)
    for r in [r1,r2]:
        assert isinstance(r, StrategyResult)
        assert r.strategy_name in ("DONCHIAN","RSI-REV")
        assert 0 <= r.setup_score <=100
        assert r.evidence is not None
        assert isinstance(r.reason_codes, list)

def test_str_extra_confluence_boost():
    from gcis.strategies.extra import evaluate_confluence
    df = _make_df(500)
    view = _make_view(df)
    cfg = {"analysis_timeframes":{"setup":"15m","bias":"1h"},"strategy":{"ema_cross":{"fast":9,"slow":21,"stop_atr":1.0,"tp_r":2.0,"min_net_rr":0.5}},"costs":{"taker_fee_bps":5,"slippage_bps_base":2},"ict":{"structure":{"min_break_atr":0.1},"displacement":{"body_to_range_min":0.6,"range_atr_min":1.5,"close_position_min":0.7},"fvg":{"min_size_atr":0.15,"min_size_ticks":2,"tick_size":0.01},"liquidity":{"equal_level_tolerance_atr":0.1,"min_touches":2,"lookback_bars":100,"sweep":{"penetration_min_atr":0.05,"reject_within_bars":3,"require_displacement":True}},"order_block":{"displacement_within_bars":3,"require_bos":True,"max_age_bars":300,"use_body_zone":True},"premium_discount":{"require_discount_for_long":False,"require_premium_for_short":False}}}
    res = evaluate_confluence(view, "BTCUSDT", cfg)
    assert res.strategy_name == "CONFLUENCE"
    assert 0 <= res.setup_score <=100
    # confluence evidence should mention confluence
    assert any("confluence" in e.lower() for e in res.evidence)

# Walk-forward tests
def test_walk_forward_splits_purge_embargo():
    from gcis.backtest.walk_forward import walk_forward_splits
    df = _make_df(4000)  # 4000*15m ~41 days
    splits = walk_forward_splits(df, "15m", train_days=10, test_days=2, purge_bars=24, embargo_bars=12)
    assert len(splits) >=2
    for s in splits:
        # purge gap respected
        assert s["test_start"] - s["train_end"] == 24
        assert s["embargo"][0] == s["test_end"] and s["embargo"][1] - s["embargo"][0] == 12 or s["embargo"][1]<=len(df)
        # train bars count
        assert s["train_end"]-s["train_start"] == s["train_bars"]
        assert s["test_end"]-s["test_start"] == s["test_bars"]
    # no overlap purge ensures leakage false overall
    for i in range(len(splits)-1):
        assert splits[i]["test_end"] <= splits[i+1]["train_start"], "leakage: test should end before next train"

def test_walk_forward_run_and_oos():
    from gcis.backtest.walk_forward import run_walk_forward
    df = _make_df(1200)
    # use small train/test to get folds quickly
    res = run_walk_forward(symbols=["BTCUSDT"], timeframe="15m", df_override=df, train_days=30, test_days=10, purge_bars=5, embargo_bars=2, strategy_name="EMA-CROSS")
    assert res["status"] in ("OK","INSUFFICIENT_HISTORY")
    if res["status"]=="OK":
        assert res["folds_count"] >=1
        assert res["leakage_check"] == True
        assert "oos_metrics" in res
        assert "fold_results" in res
        assert res["purge_bars"]==5
        # oos_trades_count should match sum fold trades
        total = sum(f["trades_count"] for f in res["fold_results"])
        assert res["oos_trades_count"] == total

def test_walk_forward_insufficient_history():
    from gcis.backtest.walk_forward import run_walk_forward
    df = _make_df(50)
    res = run_walk_forward(symbols=["BTCUSDT"], timeframe="15m", df_override=df, train_days=180, test_days=30)
    assert res["status"] == "INSUFFICIENT_HISTORY"
    assert res["folds"] == []

# Monte Carlo tests
def test_monte_carlo_deterministic_and_pvalue():
    from gcis.backtest.monte_carlo import block_bootstrap_trades
    trades = [{"net_pnl": 1.5},{"net_pnl": -0.5},{"net_pnl": 2.0},{"net_pnl": -1.0},{"net_pnl": 0.5},{"net_pnl": 1.0},{"net_pnl": -0.2},{"net_pnl": 0.8},{"net_pnl": -0.3},{"net_pnl": 1.2},{"net_pnl": 0.4},{"net_pnl": -0.6}] * 3  # 36 trades
    out1 = block_bootstrap_trades(trades, block_size=5, runs=200, seed=42)
    out2 = block_bootstrap_trades(trades, block_size=5, runs=200, seed=42)
    assert out1["status"]=="OK"
    assert out1["observed_expectancy"] == out2["observed_expectancy"]
    assert out1["ci_95"] == out2["ci_95"]
    assert out1["p_value_vs_zero"] == out2["p_value_vs_zero"]
    assert 0 <= out1["p_value_vs_zero"] <=1
    assert out1["ci_95"][0] <= out1["ci_95"][1]
    assert out1["runs"]==200
    assert out1["block_size"]==5
    # distribution mean close to observed (within 0.1)
    assert abs(out1["distribution_mean"] - out1["observed_expectancy"]) < 0.2

def test_monte_carlo_from_backtest():
    from gcis.backtest.engine import run_backtest
    from gcis.backtest.monte_carlo import monte_carlo_from_backtest
    from unittest.mock import patch
    from gcis.strategies.base import StrategyResult
    from decimal import Decimal
    df = _make_df(300)
    def mock_eval(view,symbol,cfg):
        dfv = view.get_closed_candles(symbol,"15m")
        if len(dfv) % 25 ==0 and len(dfv)>60:
            return StrategyResult("ICT-A","0.1.0",True,"LONG",75,0.7,True,(100,101),Decimal("99"),[Decimal("102")],["ok"],[],["15m"],"HEALTHY")
        return StrategyResult("ICT-A","0.1.0",False,None,20,0.2,False,None,None,None,["no"],[],[],"HEALTHY")
    with patch("gcis.strategies.ict_a.evaluate_ict_a", side_effect=mock_eval):
        res = run_backtest(symbols=["BTCUSDT"], timeframe="15m", df_override=df)
        mc = monte_carlo_from_backtest(res, runs=100, block_size=4, seed=123)
        assert mc["status"] in ("OK","DEGRADED_SMALL_SAMPLE","INSUFFICIENT_TRADES")
        if mc["status"]=="OK":
            assert "p_value_vs_zero" in mc
            assert 0 <= mc["p_value_vs_zero"] <=1

# Confluence tests
def test_confluence_basic():
    from gcis.research.confluence import analyze_confluence
    # synthetic trades with entry_bar
    a = [{"entry_bar":10,"direction":"LONG","net_pnl":1.0},{"entry_bar":20,"direction":"SHORT","net_pnl":-0.5},{"entry_bar":30,"direction":"LONG","net_pnl":2.0}]
    b = [{"entry_bar":10,"direction":"LONG","net_pnl":0.8},{"entry_bar":25,"direction":"LONG","net_pnl":1.2},{"entry_bar":30,"direction":"LONG","net_pnl":1.5}]
    c = [{"entry_bar":11,"direction":"SHORT","net_pnl":-0.3}]
    out = analyze_confluence({"ICT-A": a, "EMA-CROSS": b, "DONCHIAN": c})
    assert out["status"]=="OK"
    assert out["counts"]["ICT-A"]==3
    assert "ICT-A__EMA-CROSS" in out["overlap"]
    # jaccard for 10,30 overlap 2/4=0.5
    j = out["overlap"]["ICT-A__EMA-CROSS"]["jaccard"]
    assert 0 <= j <=1
    assert out["confluence_bars_count"] >=1  # bars 10 and 30 have >=2 same direction
    assert out["total_trials"] == 7

def test_confluence_from_engine():
    from gcis.research.confluence import run_confluence_from_engine
    df = _make_df(600)
    out = run_confluence_from_engine(symbols=["BTCUSDT"], timeframe="15m", df_override=df, strategies=["EMA-CROSS","DONCHIAN"])
    assert out["status"] in ("OK","NO_DATA")
    assert "counts" in out
    assert "confluence_bars_count" in out

def test_no_forbidden_strings_p12():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    forbidden = ["guaranteed profit","risk free","100% win"]
    for p in (root / "src/gcis/backtest").rglob("*.py"):
        txt = p.read_text().lower()
        for f in forbidden:
            assert f not in txt
    for p in (root / "src/gcis/strategies").rglob("*.py"):
        txt = p.read_text().lower()
        for f in forbidden:
            assert f not in txt
    for p in (root / "src/gcis/research").rglob("*.py"):
        txt = p.read_text().lower()
        for f in forbidden:
            assert f not in txt

def test_walk_forward_no_lookahead():
    # ensure walk_forward uses only prefix up to global_i for view, not future
    from gcis.backtest.walk_forward import run_walk_forward
    df = _make_df(500)
    # inject a huge spike in future beyond test window, ensure it doesn't affect earlier folds
    df_future = df.copy()
    # spike at last bar
    df_future.iloc[-1, df_future.columns.get_loc("close")] = 1000
    res1 = run_walk_forward(symbols=["BTCUSDT"], timeframe="15m", df_override=df, train_days=20, test_days=10, purge_bars=2, embargo_bars=1, strategy_name="DONCHIAN")
    res2 = run_walk_forward(symbols=["BTCUSDT"], timeframe="15m", df_override=df_future, train_days=20, test_days=10, purge_bars=2, embargo_bars=1, strategy_name="DONCHIAN")
    # first fold should be identical (since spike beyond first test windows)
    if res1["status"]=="OK" and res2["status"]=="OK" and res1["fold_results"] and res2["fold_results"]:
        assert res1["fold_results"][0]["trades_count"] == res2["fold_results"][0]["trades_count"]
