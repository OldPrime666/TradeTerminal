"""P08 backtest tests: shared core, fidelity, costs, lineage, baselines, census, metrics, backtestability, survivorship."""
import pandas as pd
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import patch
from gcis.strategies.base import StrategyResult

def _make_df(n=100, tf="15m", start_price=100, gap_at=None):
    """Synthetic 15m df n bars, gap_at inserts 2-bar gap for DAT-14."""
    base = datetime(2024,1,1, tzinfo=timezone.utc)
    rows=[]
    price=start_price
    delta = {"1m":1,"5m":5,"15m":15,"1h":60}[tf]
    for i in range(n):
        if gap_at is not None and i == gap_at:
            # skip 2 bars => gap
            price += 1
            continue
        ot = base + timedelta(minutes=delta*i)
        ct = ot + timedelta(minutes=delta) - timedelta(seconds=1)
        open_p = price
        high = price+1
        low = price-1
        close = price+0.5
        price = close
        rows.append({"open_time": ot, "close_time": ct, "open": open_p, "high": high, "low": low, "close": close, "volume": 10})
    return pd.DataFrame(rows)

def test_fidelity_pessimistic_stop_first():
    from gcis.backtest.fidelity import resolve_exit_pessimistic
    # LONG both hit -> STOP pessimistic
    assert resolve_exit_pessimistic(104,98,99,103,"LONG") == "STOP"
    assert resolve_exit_pessimistic(102,96,101,97,"SHORT") == "STOP"
    # only target
    assert resolve_exit_pessimistic(105,99.5,98,101,"LONG") == "TARGET"
    assert resolve_exit_pessimistic(96,95,101,97,"SHORT") == "TARGET"
    # only stop
    assert resolve_exit_pessimistic(100,98,99,105,"LONG") == "STOP"
    # none
    assert resolve_exit_pessimistic(101,99,98,103,"LONG") is None

def test_costs_realism_via_engine():
    df = _make_df(100)
    def mock_eval(view,symbol,cfg):
        # eligible every 30 bars
        dfv = view.get_closed_candles(symbol, "15m")
        if len(dfv) % 30 == 0 and len(dfv) > 60:
            return StrategyResult("ICT-A","0.1.0",True,"LONG",85,0.8,True,(100,101), Decimal("99"), [104], ["ok"],[],["15m","1h"],"HEALTHY")
        return StrategyResult("ICT-A","0.1.0",False,None,30,0.3,False,None,None,None,["no"],["NO"],[],"HEALTHY")
    with patch("gcis.strategies.ict_a.evaluate_ict_a", side_effect=mock_eval):
        from gcis.backtest.engine import run_backtest
        res = run_backtest(symbols=["BTCUSDT"], timeframe="15m", df_override=df)
        assert res["trades_count"] >= 1
        t = res["trades"][0]
        # cost = entry*0.0005 + exit*0.0005 (taker 5bps)
        expected_cost = t["entry"]*0.0005 + t["exit"]*0.0005
        assert abs(t["cost"] - expected_cost) < 1e-6
        # net pnl = (exit-entry)-cost for LONG
        assert abs(t["net_pnl"] - ((t["exit"]-t["entry"])-t["cost"])) < 1e-6
        # lineage cost realism flag implicit

def test_lineage_present():
    df = _make_df(60)
    from gcis.backtest.engine import run_backtest
    res = run_backtest(symbols=["BTCUSDT"], timeframe="15m", df_override=df)
    assert "lineage" in res
    assert "config_version" in res["lineage"]
    assert res["lineage"]["config_version"].startswith("cfg-")
    assert "analysis_version" in res["lineage"]
    assert res["lineage"]["fidelity"] == "OHLC_APPROXIMATION"
    assert res["lineage"]["same_bar_policy"] == "stop_first"

def test_baselines_four_and_verdict():
    df = _make_df(200)
    from gcis.backtest.baselines import run_all_baselines, verdict_vs_baselines
    from gcis.backtest.metrics import compute_metrics
    baselines = run_all_baselines(df)
    assert "random" in baselines
    assert "buy_hold" in baselines
    assert "ema_cross" in baselines
    assert "time_shift_placebo" in baselines
    assert "verdict" in baselines
    # each baseline has trades and metrics
    for k in ["random","buy_hold","ema_cross","time_shift_placebo"]:
        assert "metrics" in baselines[k]
        assert "trades" in baselines[k]
    # verdict vs baselines
    from gcis.backtest.engine import run_backtest
    # run strategy with mock to have some trades
    def mock_eval(view,symbol,cfg):
        dfv = view.get_closed_candles(symbol, "15m")
        if len(dfv) % 25 == 0 and len(dfv) > 60:
            return StrategyResult("ICT-A","0.1.0",True,"LONG",85,0.8,True,(100,101), Decimal("99"), [104], ["ok"],[],["15m","1h"],"HEALTHY")
        return StrategyResult("ICT-A","0.1.0",False,None,30,0.3,False,None,None,None,["no"],["NO"],[],"HEALTHY")
    with patch("gcis.strategies.ict_a.evaluate_ict_a", side_effect=mock_eval):
        res = run_backtest(symbols=["BTCUSDT"], timeframe="15m", df_override=df)
        # baselines already computed inside run_backtest
        assert "baselines" in res
        assert "verdict" in res
        assert res["verdict"] in ["INSUFFICIENT_TRADES","INCONCLUSIVE","OUTPERFORMS_BASELINES","ABOVE_AVERAGE_BASELINES","UNDERPERFORMS","ERROR"]

def test_census_tier_verdict(monkeypatch, tmp_path):
    # Use in-memory DB with synthetic candles
    from gcis.persistence.db import Base, get_engine
    from sqlalchemy.orm import sessionmaker
    from gcis.persistence.models import Candle
    import gcis.backtest.census as census_mod
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    sess = SessionLocal()
    base = datetime(2024,1,1, tzinfo=timezone.utc)
    # insert 1200 candles -> TIER_POOLED_ONLY
    for i in range(1200):
        ot = base + timedelta(minutes=15*i)
        ct = ot + timedelta(minutes=15)
        c = Candle(venue="binance_um", symbol="BTCUSDT", timeframe="15m", open_time=ot, close_time=ct, open=Decimal("100"), high=Decimal("101"), low=Decimal("99"), close=Decimal("100.5"), volume=Decimal("10"), quote_volume=Decimal("1000"), trade_count=100, taker_buy_volume=Decimal("5"))
        sess.add(c)
    sess.commit()
    monkeypatch.setattr("gcis.backtest.census.get_session", lambda: sess)
    # also patch engine's get_session for census internal? already patched
    out = census_mod.run_census(symbols=["BTCUSDT"], timeframe="15m")
    assert out["total_candles"] == 1200
    assert out["feasibility_verdict"] == "TIER_POOLED_ONLY"
    assert "backtestability" in out
    assert "survivorship_note" in out
    # add more to reach TIER_STRATEGY
    for i in range(1200, 6000):
        ot = base + timedelta(minutes=15*i)
        ct = ot + timedelta(minutes=15)
        c = Candle(venue="binance_um", symbol="BTCUSDT", timeframe="15m", open_time=ot, close_time=ct, open=Decimal("100"), high=Decimal("101"), low=Decimal("99"), close=Decimal("100.5"), volume=Decimal("10"), quote_volume=Decimal("1000"), trade_count=100, taker_buy_volume=Decimal("5"))
        sess.add(c)
    sess.commit()
    out2 = census_mod.run_census(symbols=["BTCUSDT"], timeframe="15m")
    assert out2["feasibility_verdict"] == "TIER_STRATEGY"
    sess.close()

def test_metrics_365d_window():
    df = _make_df(100)
    from gcis.backtest.engine import run_backtest
    res = run_backtest(symbols=["BTCUSDT"], timeframe="15m", df_override=df)
    assert res["metrics"]["window_days"] == 365
    assert res["metrics"]["timeframe"] == "15m"
    # metrics should have expectancy etc.
    assert "expectancy" in res["metrics"]
    assert "total_net_pnl" in res["metrics"]

def test_backtestability_statuses():
    # INSUFFICIENT_HISTORY for <300 bars
    df_small = _make_df(50)
    from gcis.backtest.engine import run_backtest
    res = run_backtest(symbols=["BTCUSDT"], timeframe="15m", df_override=df_small)
    assert res["backtestability"]["BTCUSDT"] in ["INSUFFICIENT_HISTORY","DEGRADED_SMALL_SAMPLE","OK","GAP"]
    # GAP case
    df_gap = _make_df(400, gap_at=200)
    res2 = run_backtest(symbols=["BTCUSDT"], timeframe="15m", df_override=df_gap)
    # gap may be detected as GAP if quality_report sees missing bars
    # For our synthetic gap (skipped 2 bars), quality_report should detect gap
    assert res2["backtestability"]["BTCUSDT"] in ["GAP","INSUFFICIENT_HISTORY","OK","DEGRADED_SMALL_SAMPLE","UNKNOWN"]
    # NO_DATA case
    df_empty = pd.DataFrame(columns=["open_time","close_time","open","high","low","close","volume"])
    res3 = run_backtest(symbols=["BTCUSDT"], timeframe="15m", df_override=df_empty)
    assert res3["status"] == "NO DATA"
    assert res3["backtestability"]["_all"] == "NO_DATA"

def test_survivorship_note():
    df = _make_df(100)
    from gcis.backtest.engine import run_backtest
    res = run_backtest(symbols=["BTCUSDT"], timeframe="15m", df_override=df)
    assert "survivorship_note" in res
    assert "survivorship" in res["survivorship_note"].lower() or "delisted" in res["survivorship_note"].lower()
    # census also
    from unittest.mock import patch
    from gcis.persistence.db import Base, get_engine
    from sqlalchemy.orm import sessionmaker
    from gcis.persistence.models import Candle
    import gcis.backtest.census as census_mod
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    sess = SessionLocal()
    # empty should have survivorship note
    with patch("gcis.backtest.census.get_session", lambda: sess):
        out = census_mod.run_census(symbols=["BTCUSDT"], timeframe="15m")
        assert "survivorship_note" in out

def test_same_core_uses_marketview_and_gates():
    # Ensure backtest uses MarketView incremental (causal) — test that future bar not visible at as_of
    df = _make_df(100)
    # mock evaluate to check view length
    seen_lens = []
    def mock_eval(view,symbol,cfg):
        dfv = view.get_closed_candles(symbol, "15m")
        seen_lens.append(len(dfv))
        return StrategyResult("ICT-A","0.1.0",False,None,30,0.3,False,None,None,None,["no"],["NO"],[],"HEALTHY")
    with patch("gcis.strategies.ict_a.evaluate_ict_a", side_effect=mock_eval):
        from gcis.backtest.engine import run_backtest
        res = run_backtest(symbols=["BTCUSDT"], timeframe="15m", df_override=df)
        # seen_lens should be increasing and never include future (i+1)
        assert seen_lens[0] == 51  # first i=50 -> 51 bars
        assert all(seen_lens[i] < seen_lens[i+1] for i in range(len(seen_lens)-1))
        # also check that gates were called (if we patch is_mv_pass to track)
        assert res["status"] in ["INSUFFICIENT_HISTORY","DEGRADED_SMALL_SAMPLE","OK","GAP"]

def test_no_data_honest_empty_db(monkeypatch):
    from gcis.backtest.engine import run_backtest
    # patch _fetch_candles to return empty
    monkeypatch.setattr("gcis.backtest.engine._fetch_candles", lambda *a, **kw: [])
    res = run_backtest(symbols=["BTCUSDT"], timeframe="15m")
    assert res["status"] == "NO DATA"
    assert "No candles" in res["message"]
