"""P17 DOM + CCXT twin + depth recorder + alerts"""
import tempfile
import pathlib
import json
from datetime import datetime, timezone, timedelta

def test_ccxt_twin_parity():
    from gcis.data.exchange.ccxt_adapter import compare_twin_parity
    # native contracts fixture (as would be from binance_um parse)
    native = [
        {"symbol":"BTCUSDT","base":"BTC","quote":"USDT","family":"linear","contract_type":"PERPETUAL","status":"TRADING"},
        {"symbol":"ETHUSDT","base":"ETH","quote":"USDT","family":"linear","contract_type":"PERPETUAL","status":"TRADING"},
        {"symbol":"SOLUSDT","base":"SOL","quote":"USDT","family":"linear","contract_type":"PERPETUAL","status":"TRADING"},
    ]
    ccxt = [
        {"symbol":"BTCUSDT","base":"BTC","quote":"USDT","family":"linear","contract_type":"PERPETUAL","status":"TRADING"},
        {"symbol":"ETHUSDT","base":"ETH","quote":"USDT","family":"linear","contract_type":"PERPETUAL","status":"TRADING"},
        {"symbol":"SOLUSDT","base":"SOL","quote":"USDT","family":"linear","contract_type":"PERPETUAL","status":"TRADING"},
    ]
    report = compare_twin_parity(native, ccxt)
    assert report["native_count"]==3
    assert report["ccxt_count"]==3
    assert report["matched"]==3
    assert report["parity_ok"]==True
    assert report["missing_in_ccxt"]==[]
    # mismatch case
    ccxt2 = ccxt[:2]  # missing SOL
    report2 = compare_twin_parity(native, ccxt2)
    assert report2["parity_ok"]==False
    assert "SOLUSDT" in report2["missing_in_ccxt"]

def test_ccxt_parse_helper():
    from gcis.data.exchange.ccxt_adapter import CcxtBinanceUMAdapter
    adapter = CcxtBinanceUMAdapter()
    markets = [
        {"id":"BTCUSDT","base":"BTC","quote":"USDT","settle":"USDT","active":True},
        {"id":"ETHUSDT","base":"ETH","quote":"USDT","settle":"USDT","active":True},
    ]
    parsed = adapter.parse_ccxt_markets(markets)
    assert len(parsed)==2
    assert parsed[0]["symbol"]=="BTCUSDT"
    assert parsed[0]["source"]=="ccxt_parsed"

def test_depth_recorder_append_and_stats(tmp_path):
    from gcis.data.recorder import depth as depth_mod
    # patch root
    orig_root = depth_mod.DEPTH_ROOT
    depth_mod.DEPTH_ROOT = tmp_path / "depth"
    try:
        now = datetime.now(timezone.utc)
        bids = [[100.0,1.0],[99.5,2.0]]
        asks = [[101.0,1.0],[101.5,2.0]]
        path = depth_mod.append_depth("binance_um","BTCUSDT", bids, asks, seq=1, ts=now)
        assert path.exists()
        # second append same day
        path2 = depth_mod.append_depth("binance_um","BTCUSDT", bids, asks, seq=2, ts=now)
        assert path2 == path  # same day same file
        files = depth_mod.list_depth("binance_um","BTCUSDT", since_days=30)
        assert len(files)==1
        stats = depth_mod.depth_stats(path)
        assert stats["lines"]==2
        assert stats["bytes"]>0
        assert stats["latest_timestamp"] is not None
        # purge not yet (retention 30)
        deleted = depth_mod.purge_expired(retention_days=30)
        assert deleted==0  # still fresh
        # force old via mtime hack
        import time, os
        old_time = time.time() - 40*86400
        os.utime(path, (old_time, old_time))
        deleted2 = depth_mod.purge_expired(retention_days=30)
        assert deleted2==1
        assert not path.exists()
    finally:
        depth_mod.DEPTH_ROOT = orig_root

def test_depth_list_filters():
    from gcis.data.recorder import depth as dmod
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as td:
        orig = dmod.DEPTH_ROOT
        dmod.DEPTH_ROOT = pathlib.Path(td) / "depth"
        try:
            now = datetime.now(timezone.utc)
            dmod.append_depth("binance_um","BTCUSDT", [[100,1]], [[101,1]], ts=now)
            dmod.append_depth("binance_um","ETHUSDT", [[200,1]], [[201,1]], ts=now)
            dmod.append_depth("bybit","BTCUSDT", [[100,1]], [[101,1]], ts=now)
            all_files = dmod.list_depth(since_days=30)
            assert len(all_files)==3
            btc_binance = dmod.list_depth("binance_um","BTCUSDT")
            assert len(btc_binance)==1
            binance_all = dmod.list_depth("binance_um")
            assert len(binance_all)==2
        finally:
            dmod.DEPTH_ROOT = orig

def test_alerts_evaluation():
    from gcis.ops import metrics as metmod
    from gcis.ops.alerts import evaluate_alerts
    # fresh rollup
    rollup = metmod.get_metrics_rollup()
    # clear state
    rollup.ingest_to_persist_ms.clear()
    rollup.bundle_latency_s.clear()
    rollup.candle_to_signal_s.clear()
    # inject lag > budgets
    for _ in range(5):
        rollup.record_ingest_to_persist(500)  # >250
        rollup.record_bundle_latency(25)  # >20
        rollup.record_candle_to_signal(5)  # >3
    alerts = evaluate_alerts()
    names = [a["alert"] for a in alerts]
    assert "INGEST_LAG" in names
    assert "BUNDLE_LAG" in names
    assert "CANDLE_LAG" in names
    # secondary discrepancy warn
    sec = {"status":"WARN","bps":35}
    alerts2 = evaluate_alerts(secondary_check=sec)
    assert any(a["alert"]=="MARKET_DATA_DISCREPANCY" for a in alerts2)
    # news veto
    news = {"blocked": True, "reason":"MACRO_BLACKOUT high"}
    alerts3 = evaluate_alerts(news_veto=news)
    assert any(a["alert"]=="NEWS_BLACKOUT" for a in alerts3)
    # clean
    rollup.ingest_to_persist_ms.clear()
    rollup.bundle_latency_s.clear()
    rollup.candle_to_signal_s.clear()

def test_alerts_dispatch():
    from gcis.ops.alerts import dispatch_alerts
    from gcis.ops.notifications import get_notification_manager
    mgr = get_notification_manager()
    # clear queue
    mgr.queue.clear()
    alerts = [{"alert":"TEST","level":"INFO","detail":"hello","timestamp":"now"}]
    res = dispatch_alerts(alerts)
    assert res["dispatched"]==1
    assert len(res["alerts"])==1

def test_orderbook_depth_integration():
    from gcis.market.orderbook import get_book, clear_books
    clear_books()
    ob = get_book("ETHUSDT")
    now = datetime.now(timezone.utc)
    ob.apply_snapshot([[200,1],[199,1]], [[201,1],[202,1]], ts=now)
    snap = ob.to_snapshot()
    assert snap["symbol"]=="ETHUSDT"
    assert snap["mid"]==200.5
    # record to depth
    from gcis.data.recorder import depth as dmod
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as td:
        orig = dmod.DEPTH_ROOT
        dmod.DEPTH_ROOT = pathlib.Path(td)/"depth"
        try:
            path = dmod.append_depth("binance_um","ETHUSDT", snap["bids"], snap["asks"], ts=now)
            assert path.exists()
            stats = dmod.depth_stats(path)
            assert stats["lines"]==1
        finally:
            dmod.DEPTH_ROOT = orig
    clear_books()

def test_no_forbidden_strings_p17():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    forb=["guaranteed profit","risk free","100% win"]
    for p in (root / "src/gcis/data/exchange").rglob("ccxt_adapter.py"):
        txt=p.read_text().lower()
        for f in forb:
            assert f not in txt
    for p in (root / "src/gcis/data/recorder").rglob("depth.py"):
        txt=p.read_text().lower()
        for f in forb:
            assert f not in txt
