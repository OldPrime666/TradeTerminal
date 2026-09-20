"""P19 Consolidation: DAT-16 trade archive + BKT-11 consistency"""
import tempfile, pathlib, json
from datetime import datetime, timezone, timedelta

def test_trade_archive_append_and_dedup(tmp_path):
    from gcis.data.archive import trade_archive as ta
    orig = ta.TRADE_ROOT
    ta.TRADE_ROOT = tmp_path / "trade_archive"
    try:
        now = datetime.now(timezone.utc)
        trades = [
            {"aggTradeId": 1, "price": "100.0", "qty": "0.1", "timestamp": 1000, "isBuyerMaker": True},
            {"aggTradeId": 2, "price": "101.0", "qty": "0.2", "timestamp": 1001, "isBuyerMaker": False},
        ]
        path = ta.append_trades("binance_um","BTCUSDT", trades, dt=now)
        assert path.exists()
        # duplicate append same ids => no new lines
        path2 = ta.append_trades("binance_um","BTCUSDT", trades, dt=now)
        assert path2 == path
        # count lines =2 not 4
        with open(path) as f:
            lines = f.readlines()
        assert len(lines)==2
        # add new id 3
        path3 = ta.append_trades("binance_um","BTCUSDT", [{"aggTradeId":3,"price":"102","qty":"0.1","timestamp":1002}], dt=now)
        with open(path) as f:
            assert len(f.readlines())==3
        files = ta.list_trade_archive("binance_um","BTCUSDT", since_days=30)
        assert len(files)==1
        stats = ta.trade_archive_stats("binance_um","BTCUSDT")
        assert stats["trades"]==3
        assert stats["files"]==1
        # purge not yet
        assert ta.purge_expired(30)==0
        # force old
        import time, os
        old = time.time() - 40*86400
        os.utime(path, (old, old))
        assert ta.purge_expired(30)==1
        assert not path.exists()
    finally:
        ta.TRADE_ROOT = orig

def test_backtest_consistency():
    from gcis.backtest.consistency import compare_paper_backtest, funding_consistency_check, effective_leverage_consistency
    paper = [{"entry":100,"net_pnl":1.0},{"entry":100,"net_pnl":0.5}]
    back = [{"entry":100,"net_pnl":0.9},{"entry":100,"net_pnl":0.45}]
    # paper avg bps: (1/100*10000=100, 0.5=>50 avg 75), back 90 and 45 avg 67.5 => divergence 7.5 <15 => consistent
    res = compare_paper_backtest(paper, back, threshold_bps=15)
    assert res["status"]=="CONSISTENT"
    assert res["flag"]==False
    # large divergence
    paper2 = [{"entry":100,"net_pnl":5.0}]  # 500 bps
    back2 = [{"entry":100,"net_pnl":0.1}]  # 10 bps => divergence 490 >15 => diverged
    res2 = compare_paper_backtest(paper2, back2)
    assert res2["flag"]==True and res2["status"]=="DIVERGED"
    # funding
    fund = funding_consistency_check(10, 20, 0.15)
    assert "ratio_R" in fund
    # leverage
    lev = effective_leverage_consistency(15000, 10000, 3.0)
    assert lev["leverage"]==1.5 and lev["flag"]==False
    lev2 = effective_leverage_consistency(40000, 10000, 3.0)
    assert lev2["flag"]==True

def test_no_forbidden_p19():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    forb=["guaranteed profit","risk free","100% win"]
    for p in (root / "src/gcis/data/archive").rglob("trade_archive.py"):
        assert all(f not in p.read_text().lower() for f in forb)
    for p in (root / "src/gcis/backtest").rglob("consistency.py"):
        assert all(f not in p.read_text().lower() for f in forb)
