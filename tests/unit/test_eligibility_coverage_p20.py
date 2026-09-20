"""P20 Eligibility + Coverage DAT-19"""
from datetime import datetime, timezone, timedelta

def test_eligibility_filters():
    from gcis.data.eligibility import is_eligible, filter_eligible
    now = datetime.now(timezone.utc)
    contract = {"symbol":"BTCUSDT","status":"TRADING","listing_time": now - timedelta(days=20)}
    stats_ok = {"quote_volume": 10000000, "spread_bps": 10, "open_interest_usdt": 2000000}
    res = is_eligible(contract, stats_ok, now=now)
    assert res["eligible"]==True
    # volume fail
    stats_vol_fail = {"quote_volume": 1000, "spread_bps": 5, "open_interest_usdt": 2000000}
    res2 = is_eligible(contract, stats_vol_fail, now=now)
    assert res2["eligible"]==False and any("VOL" in r for r in res2["reasons"])
    # spread fail
    stats_spread = {"quote_volume": 10000000, "spread_bps": 20, "open_interest_usdt": 2000000}
    res3 = is_eligible(contract, stats_spread, now=now)
    assert res3["eligible"]==False
    # age fail
    contract_new = {"symbol":"NEWUSDT","status":"TRADING","listing_time": now - timedelta(days=5)}
    res4 = is_eligible(contract_new, stats_ok, now=now)
    assert res4["eligible"]==False
    # OI fail
    stats_oi = {"quote_volume": 10000000, "spread_bps": 5, "open_interest_usdt": 50000}
    res5 = is_eligible(contract, stats_oi, now=now)
    assert res5["eligible"]==False
    # status not trading
    contract_bad = {"symbol":"BADUSDT","status":"HALTED","listing_time": now - timedelta(days=20)}
    res6 = is_eligible(contract_bad, stats_ok, now=now)
    assert res6["eligible"]==False
    # batch filter
    contracts = [contract, contract_new, contract_bad]
    stats_map = {"BTCUSDT": stats_ok, "NEWUSDT": stats_ok, "BADUSDT": stats_ok}
    batch = filter_eligible(contracts, stats_map, now=now)
    assert batch["eligible_count"]==1
    assert batch["total"]==3
    assert batch["ineligible_count"]==2

def test_coverage_report():
    from gcis.data.coverage import coverage_report, banner_coverage_text
    all_contracts = [{"symbol": f"S{i}USDT", "status":"TRADING"} for i in range(10)]
    eligible = all_contracts[:8]  # 8 eligible
    counts = {f"S{i}USDT": 500 for i in range(5)}  # 5 have enough history
    # plus 3 eligible without history
    report = coverage_report(all_contracts, eligible, counts, min_history_bars=300)
    assert report["total_listed"]==10
    assert report["eligible"]==8
    assert report["analysed"]==5
    assert report["coverage_ratio"]==0.5
    assert report["status"] in ("LOW_COVERAGE","DEGRADED","HEALTHY","NO_DATA")
    text = banner_coverage_text(report)
    assert "5/10" in text
    # healthy threshold 0.98
    counts2 = {f"S{i}USDT": 500 for i in range(10)}
    report2 = coverage_report(all_contracts, all_contracts, counts2, 300)
    assert report2["coverage_ratio"]==1.0
    assert report2["status"]=="HEALTHY"
    # no data
    report3 = coverage_report([], [], {}, 300)
    assert report3["status"]=="NO_DATA"

def test_coverage_with_no_candles():
    from gcis.data.coverage import coverage_report
    all_contracts = [{"symbol":"BTCUSDT"}]
    report = coverage_report(all_contracts, all_contracts, {}, 300)
    assert report["analysed"]==0
    assert report["coverage_ratio"]==0.0

def test_no_forbidden_p20():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    forb=["guaranteed profit","risk free","100% win"]
    for p in (root / "src/gcis/data").rglob("eligibility.py"):
        assert all(f not in p.read_text().lower() for f in forb)
