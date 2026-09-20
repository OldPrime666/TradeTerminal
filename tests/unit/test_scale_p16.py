"""P16 Scalability ARC-20: sharded WS prioritised scheduling + bundle budget + incremental + DOM stub"""
from datetime import datetime, timezone, timedelta
import pandas as pd

def test_prioritise_symbols_order():
    from gcis.data.transport.scheduler import prioritise_symbols
    syms = ["AAAUSDT","BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT"]
    landing = {"BTCUSDT"}
    scanner = {"ETHUSDT","SOLUSDT"}
    level2 = {"XRPUSDT"}
    in_risk = {"AAAUSDT"}
    # priority landing > scanner > level2 > in_risk > other? Actually other is last, in_risk before other
    # so order: BTC (landing), ETH,SOL (scanner alphabetical), XRP (level2), AAA (in_risk)
    res = prioritise_symbols(syms, landing_set=landing, scanner_set=scanner, level2_set=level2, in_risk_set=in_risk)
    assert res[0]=="BTCUSDT"
    assert res[1]=="ETHUSDT"
    assert res[2]=="SOLUSDT"
    assert res[3]=="XRPUSDT"
    assert res[4]=="AAAUSDT"
    # operator_pins promoted to landing
    res2 = prioritise_symbols(syms, landing_set=set(), scanner_set=scanner, operator_pins={"SOLUSDT"})
    assert res2[0]=="SOLUSDT"  # pinned to landing
    # deterministic alphabetical within tier
    res3 = prioritise_symbols(["ZZZ","AAA","BBB"], scanner_set={"ZZZ","AAA","BBB"})
    assert res3==["AAA","BBB","ZZZ"]

def test_schedule_bundles_budget():
    from gcis.data.transport.scheduler import schedule_bundles
    syms = [f"S{i}USDT" for i in range(100)]
    # per symbol cost = 50 +6*2=62ms, 100 symbols => 6200ms, budget 20s => all OK
    res = schedule_bundles(syms, bundle_latency_budget_s=20, per_symbol_ms=50, candles_per_symbol=6)
    assert res["status"]=="OK"
    assert len(res["processed"])==100
    assert len(res["not_subscribed"])==0
    # small budget 1s => only ~16 processed (1000ms/62 ~16)
    res2 = schedule_bundles(syms, bundle_latency_budget_s=1, per_symbol_ms=50, candles_per_symbol=6)
    assert res2["status"]=="ANALYSIS_LAG"
    assert len(res2["processed"])==16  # 1000/62=16
    assert len(res2["not_subscribed"])==84
    assert res2["total_ms"] <= 1000

def test_plan_with_priority_integrated():
    from gcis.data.transport.scheduler import plan_with_priority
    syms = ["BTCUSDT","ETHUSDT","SOLUSDT","ADAUSDT"]
    landing = {"BTCUSDT"}
    scanner = {"ETHUSDT"}
    focus = ["BTCUSDT"]
    out = plan_with_priority(syms, focus_symbols=focus, landing=landing, scanner=scanner, budget_s=20)
    assert out["prioritized"][0]=="BTCUSDT"
    assert "plan" in out and "klines_1m" in out["plan"]
    assert "schedule" in out
    assert out["schedule"]["status"] in ("OK","ANALYSIS_LAG")
    # shard summary
    assert out["shard_summary"]["klines_1m"]["streams"]==4  # 4 symbols => 4 streams

def test_incremental_engine_affected_and_cached():
    from gcis.market.incremental import IncrementalEngine
    # make df
    base = datetime(2024,1,1, tzinfo=timezone.utc)
    def make_df(n, last_price):
        rows=[]
        for i in range(n):
            ot = base+timedelta(minutes=15*i)
            ct = ot+timedelta(minutes=15)-timedelta(seconds=1)
            rows.append({"open_time": ot, "close_time": ct, "open":100, "high":101, "low":99, "close": last_price, "volume":10})
        return pd.DataFrame(rows)
    eng = IncrementalEngine()
    df = make_df(60, 100.0)
    as_of = df["close_time"].iloc[-1] + timedelta(seconds=1)
    # first update affected
    r1 = eng.update("BTCUSDT","15m", df, as_of, lambda: {"score": 10})
    assert r1["affected"]==True and r1["cached"]==False
    assert eng.processed_count==1
    # same df same as_of -> not affected (latest close same)
    r2 = eng.update("BTCUSDT","15m", df, as_of, lambda: {"score": 99})
    assert r2["affected"]==False and r2["cached"]==True
    assert r2["result"]["score"]==10  # cached old
    assert eng.skipped_count==1
    # new df with later close => affected
    df2 = make_df(61, 101.0)  # one more bar
    as_of2 = df2["close_time"].iloc[-1] + timedelta(seconds=1)
    r3 = eng.update("BTCUSDT","15m", df2, as_of2, lambda: {"score": 20})
    assert r3["affected"]==True
    assert r3["result"]["score"]==20
    # bundle update
    df_dict = {"BTCUSDT": df2, "ETHUSDT": make_df(60, 100.0)}
    bundle = eng.bundle_update(["BTCUSDT","ETHUSDT"], "15m", df_dict, as_of2, lambda s: {"sym": s})
    assert "stats" in bundle
    assert bundle["stats"]["total"]==2

def test_incremental_invalidate():
    from gcis.market.incremental import IncrementalEngine
    base = datetime(2024,1,1, tzinfo=timezone.utc)
    def make_df(n):
        rows=[{"open_time": base+timedelta(minutes=15*i), "close_time": base+timedelta(minutes=15*(i+1)), "open":100, "high":101, "low":99, "close":100, "volume":10} for i in range(n)]
        return pd.DataFrame(rows)
    eng = IncrementalEngine()
    df = make_df(60)
    as_of = base+timedelta(days=1)
    eng.update("BTCUSDT","15m", df, as_of, lambda: {"v":1})
    assert len(eng.cache)==1
    eng.invalidate("BTCUSDT")
    assert len(eng.cache)==0

def test_orderbook_mid_spread_freshness_and_imbalance():
    from gcis.market.orderbook import OrderBook, get_book, clear_books
    clear_books()
    ob = get_book("BTCUSDT")
    # snapshot: bids 100,99 asks 101,102
    ob.apply_snapshot(bids=[[100,1.5],[99,2.0]], asks=[[101,1.0],[102,2.0]], seq=1, ts=datetime.now(timezone.utc))
    assert float(ob.best_bid())==100
    assert float(ob.best_ask())==101
    assert float(ob.mid_price())==100.5
    bps = ob.spread_bps()
    # spread = (101-100)/100.5*10000 ~99.5 bps
    assert 99 < bps < 100
    imb = ob.imbalance()
    # bid vol 3.5 ask vol 3.0 => (3.5-3)/(6.5)=0.076
    assert abs(imb - 0.076) < 0.01
    assert ob.freshness_status()=="HEALTHY"
    # stale
    old = datetime.now(timezone.utc) - timedelta(seconds=10)
    ob.apply_snapshot(bids=[[100,1]], asks=[[101,1]], ts=old)
    assert ob.freshness_status()=="STALE"
    old2 = datetime.now(timezone.utc) - timedelta(seconds=40)
    ob.apply_snapshot(bids=[[100,1]], asks=[[101,1]], ts=old2)
    assert ob.freshness_status()=="DISCONNECTED"
    # snapshot dict
    snap = ob.to_snapshot()
    assert snap["symbol"]=="BTCUSDT"
    assert snap["mid"] is not None
    # clear
    clear_books()
    assert len(_books)==0 if ' _books' in str(dir()) else True  # dummy
    from gcis.market import orderbook as obmod
    assert len(obmod._books)==0

def test_sharding_still_180():
    from gcis.data.transport.sharding import plan_shards, shard_summary
    syms = [f"S{i}USDT" for i in range(400)]
    plan = plan_shards(syms, focus_symbols=[], max_per_conn=180)
    # klines 400 => shards 3 (180,180,40)
    assert len(plan["klines_1m"])==3
    assert sum(len(s) for s in plan["klines_1m"])==400
    summary = shard_summary(plan)
    assert summary["klines_1m"]["shards"]==3

def test_no_forbidden_strings_p16():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    forb=["guaranteed profit","risk free","100% win"]
    for p in (root / "src/gcis/data/transport").rglob("scheduler.py"):
        txt=p.read_text().lower()
        for f in forb:
            assert f not in txt
    for p in (root / "src/gcis/market").rglob("*.py"):
        txt=p.read_text().lower()
        for f in forb:
            assert f not in txt
