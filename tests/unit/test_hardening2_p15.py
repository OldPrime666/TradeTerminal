"""P15 Hardening II: VOL-01, PSY-01, notifications, RSK-04 integration into RiskManager, DAT-13 via manager"""
from datetime import datetime, timezone, timedelta

def _make_candles(n=50):
    base = datetime(2024,1,1, tzinfo=timezone.utc)
    candles=[]
    price=100
    for i in range(n):
        # create volume profile: concentrated around 100-101
        if i < 20:
            high=101; low=99; close=100.5; vol=100
        elif i < 30:
            high=102; low=100; close=101; vol=50
        else:
            high=99; low=97; close=98; vol=20
        candles.append({"open_time": base+timedelta(minutes=15*i), "close_time": base+timedelta(minutes=15*(i+1)), "open": 100, "high": high, "low": low, "close": close, "volume": vol})
    return candles

def test_volume_profile_poc_and_value_area():
    from gcis.market.volume_profile import compute_volume_profile
    candles = _make_candles(60)
    res = compute_volume_profile(candles, bins=12)
    assert res["status"]=="OK"
    assert 99 <= res["poc"] <= 101  # near 100.5
    assert res["value_area"]["low"] <= res["poc"] <= res["value_area"]["high"]
    assert res["total_volume"] >0
    assert len(res["profile"])==12
    # ensure POC has max volume among buckets
    poc_vol = res["poc_volume"]
    assert poc_vol == max(b["volume"] for b in res["profile"])
    # empty
    res2 = compute_volume_profile([], bins=12)
    assert res2["status"]=="NO_DATA"

def test_volume_profile_no_data_range():
    from gcis.market.volume_profile import compute_volume_profile
    candles=[{"high":100,"low":100,"close":100,"volume":10}]
    res = compute_volume_profile(candles, bins=12)
    assert res["status"]=="NO_RANGE"

def test_psy_proxies_fear_greed_and_regime():
    from gcis.psychology.proxies import compute_psy_proxies, psy_veto
    # trending up stable => low fear
    closes = [100 + i*0.1 for i in range(100)]  # steady up low vol
    vols = [100]*100
    res = compute_psy_proxies(closes, vols, period=20)
    assert res["status"]=="OK"
    assert 0 <= res["fear_greed"] <=100
    assert res["psy_regime"] in ("RISK_ON","NEUTRAL","RISK_OFF")
    # volatile down => high fear
    closes2 = [100 - i*0.5 if i%2==0 else 100 - i*0.3 for i in range(100)]
    res2 = compute_psy_proxies(closes2, period=20)
    assert res2["fear_greed"] > res["fear_greed"]
    # veto not blocking paper
    veto = psy_veto(res2["fear_greed"], res2["psy_regime"])
    assert veto["psy_regime"]==res2["psy_regime"]
    assert veto["blocked"]==False

def test_psy_insufficient():
    from gcis.psychology.proxies import compute_psy_proxies
    res = compute_psy_proxies([100,101], period=20)
    assert res["status"]=="INSUFFICIENT_HISTORY"
    assert res["fear_greed"]==50

def test_notifications_rate_limit_and_flush():
    from gcis.ops.notifications import NotificationManager
    import pathlib
    mgr = NotificationManager(max_per_min=2, queue_max=10)
    # ensure clean log
    # enqueue 3 quickly, only 2 should flush per minute
    now = datetime.now(timezone.utc)
    mgr.enqueue("INFO","t1","msg1")
    mgr.enqueue("INFO","t2","msg2")
    mgr.enqueue("INFO","t3","msg3")
    assert len(mgr.get_queue())==3
    out = mgr.flush(now)
    assert out["flushed"]==2
    assert out["remaining"]==1
    assert out["rate_limited"]==True
    # next minute should flush remaining
    out2 = mgr.flush(now + timedelta(seconds=61))
    assert out2["flushed"]==1
    assert out2["remaining"]==0
    # send_now
    mgr2 = NotificationManager(max_per_min=10)
    out3 = mgr2.send_now("WARN","title","body", {"symbol":"BTCUSDT"})
    assert out3["flushed"]>=1

def test_risk_manager_cluster_integration():
    from gcis.risk.manager import RiskManager
    cfg = {
        "risk": {
            "risk_per_trade_pct": 0.25,
            "max_daily_loss_pct": 1.5,
            "max_trades_per_day": 6,
            "max_concurrent_positions": 3,
            "max_open_worst_case_risk_pct": 1.5,
            "max_per_symbol_risk_pct": 0.5,
            "max_per_cluster_risk_pct": 1.0,
            "max_per_strategy_risk_pct": 1.0,
            "max_leverage_cap": 3,
            "max_effective_leverage": 3,
            "locks": {"max_spread_bps":15}
        }
    }
    rm = RiskManager(cfg)
    base_intent = {"symbol":"BTCUSDT","direction":"LONG","leverage":3,"notional":100,"cluster_id":"cluster-0"}
    daily = {"current_equity": 10000, "trades_today":0}
    exposure_ok = {"open_positions":0,"per_cluster_risk":0.2,"per_cluster":0.2}
    # simple allowed
    res = rm.check(base_intent, daily, open_risk_pct=0.2, kill_switch=False, exposure=exposure_ok)
    assert res["allowed"]==True
    # per cluster exceed
    exposure_high = {"open_positions":0,"per_cluster_risk": 1.0}  # == cap => block (>=)
    res2 = rm.check(base_intent, daily, open_risk_pct=0.2, kill_switch=False, exposure=exposure_high)
    assert res2["allowed"]==False and res2["reason_code"]=="RISK_LIMIT"
    # dict per_cluster
    exposure_dict = {"open_positions":0,"per_cluster_risk": {"cluster-0":0.9,"cluster-1":0.2}}
    # intent would push 0.9+0.25=1.15 >1.0 => block
    res3 = rm.check(base_intent, daily, open_risk_pct=0.2, kill_switch=False, exposure=exposure_dict)
    assert res3["allowed"]==False
    # news veto blocked
    intent_news = dict(base_intent)
    intent_news["news_veto_blocked"]=True
    intent_news["news_veto_reason"]="MACRO_BLACKOUT"
    res4 = rm.check(intent_news, daily, open_risk_pct=0.2, kill_switch=False, exposure=exposure_ok)
    assert res4["allowed"]==False and res4["reason_code"]=="NEWS_BLACKOUT"

def test_risk_manager_per_strategy():
    from gcis.risk.manager import RiskManager
    cfg = {"risk": {"risk_per_trade_pct":0.25,"max_trades_per_day":6,"max_concurrent_positions":3,"max_open_worst_case_risk_pct":1.5,"max_per_symbol_risk_pct":0.5,"max_per_cluster_risk_pct":1.0,"max_per_strategy_risk_pct":1.0,"max_leverage_cap":3,"max_effective_leverage":3,"locks":{"max_spread_bps":15}}}
    rm = RiskManager(cfg)
    intent = {"symbol":"ETHUSDT","leverage":2,"notional":50}
    daily={"current_equity":10000,"trades_today":0}
    exposure = {"open_positions":0,"per_cluster_risk":0.2,"per_strategy_risk":1.0}
    res = rm.check(intent, daily, 0.2, False, exposure)
    assert res["allowed"]==False

def test_no_forbidden_strings_p15():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    forb=["guaranteed profit","risk free","100% win"]
    for p in (root / "src/gcis/market").rglob("volume_profile.py"):
        txt=p.read_text().lower()
        for f in forb:
            assert f not in txt
    for p in (root / "src/gcis/psychology").rglob("*.py"):
        txt=p.read_text().lower()
        for f in forb:
            assert f not in txt
    for p in (root / "src/gcis/ops").rglob("notifications.py"):
        txt=p.read_text().lower()
        for f in forb:
            assert f not in txt
