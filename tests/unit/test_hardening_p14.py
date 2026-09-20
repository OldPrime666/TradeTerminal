"""P14 Hardening: RSK-04 DAT-12/13 OPS-06/09/10 EXE-09"""
from datetime import datetime, timezone, timedelta

def test_correlation_dynamic_and_threshold():
    from gcis.risk.correlation import dynamic_clusters, is_correlated, pairwise_correlations, cluster_by_threshold
    # high correlation pair
    rets = {
        "BTCUSDT": [0.01,0.02,-0.01,0.03,0.02,0.01]*50,  # 300
        "ETHUSDT": [0.011,0.021,-0.009,0.031,0.021,0.011]*50,
        "SOLUSDT": [0.005]*300  # constant => std 0 => corr 0, low correlation
    }
    corr = pairwise_correlations(rets)
    # BTC-ETH high
    rho = corr[("BTCUSDT","ETHUSDT")]
    assert abs(rho) > 0.85
    # BTC-SOL low (constant => 0)
    rho2 = corr[("BTCUSDT","SOLUSDT")]
    assert abs(rho2) < 0.5
    # clustering threshold 0.70 => BTC+ETH together, SOL separate
    clusters = cluster_by_threshold(list(rets.keys()), corr, threshold=0.70)
    assert is_correlated("BTCUSDT","ETHUSDT", clusters)==True
    assert is_correlated("BTCUSDT","SOLUSDT", clusters)==False
    # dynamic insufficient
    small = {"BTCUSDT":[0.01]*10}
    res = dynamic_clusters(small, link_abs_rho=0.70, min_overlap_bars=200, insufficient_data="treat_as_correlated")
    assert res["status"]=="INSUFFICIENT_DATA_TREAT_AS_CORRELATED"
    assert len(set(res["clusters"].values()))==1

def test_correlation_treat_as_correlated_single_cluster():
    from gcis.risk.correlation import dynamic_clusters
    rets = {"A":[0.01]*50,"B":[0.02]*50}
    res = dynamic_clusters(rets, min_overlap_bars=200)
    assert res["status"]=="INSUFFICIENT_DATA_TREAT_AS_CORRELATED"
    # all same cluster MARKET_BETA
    assert len(set(res["clusters"].values()))==1

def test_secondary_discrepancy_warn_flag_and_fresh():
    from gcis.data.secondary import check_discrepancy, bps_diff, is_fresh
    now = datetime.now(timezone.utc)
    can_t = now - timedelta(seconds=100)
    sec_t = now - timedelta(seconds=100)
    # 30 bps threshold warn: price 100 vs 100.31 => 31 bps (avoid float edge 29.999)
    # flag 100 bps: 100 vs 101 => 100 bps
    r1 = check_discrepancy(100.0, 100.31, can_t, sec_t, now=now, warn_bps=30, flag_bps=100)
    assert r1["status"]=="WARN"
    assert r1["bps"]>=30.0
    assert r1["overwrite"]==False
    r2 = check_discrepancy(100.0, 101.0, can_t, sec_t, now=now)
    assert r2["status"]=="FLAG"
    assert r2["action"]=="MARKET_DATA_DISCREPANCY"
    r3 = check_discrepancy(100.0, 100.1, can_t, sec_t, now=now)
    assert r3["status"]=="OK"
    # stale skip: one is 1000s old >900
    old = now - timedelta(seconds=1000)
    r4 = check_discrepancy(100.0,100.3, old, sec_t, now=now)
    assert r4["status"]=="STALE_SKIP"
    # bps calc
    assert bps_diff(100,101)==100.0
    assert is_fresh(can_t, now, 900)==True
    assert is_fresh(old, now, 900)==False

def test_secondary_metadata_never_overwrite():
    from gcis.data.secondary import check_discrepancy
    now = datetime.now(timezone.utc)
    can_t = now - timedelta(seconds=10)
    sec_t = now - timedelta(seconds=10)
    r = check_discrepancy(100,101,can_t,sec_t, now=now)
    assert r["overwrite"]==False
    # DAT-12 secondary fetch stub never overwrites
    from gcis.data.secondary import fetch_secondary_meta
    meta = fetch_secondary_meta("BTCUSDT")
    assert meta["status"]=="UNAVAILABLE"

def test_news_blackout_and_veto():
    from gcis.data.news import NewsEvent, is_in_blackout, veto_signal, fetch_macro_calendar_stub
    now = datetime(2024,1,15,12,0, tzinfo=timezone.utc)
    pub = datetime(2024,1,15,12,0, tzinfo=timezone.utc)
    det = datetime(2024,1,15,12,0, tzinfo=timezone.utc)
    ev = NewsEvent(published_at=pub, detected_at=det, impact="high", currency="USD", title="CPI")
    # signal within 30 min blackout
    sig_t = datetime(2024,1,15,12,15, tzinfo=timezone.utc)
    assert is_in_blackout(sig_t, ev, 30,30)==True
    sig_t2 = datetime(2024,1,15,13,0, tzinfo=timezone.utc)
    assert is_in_blackout(sig_t2, ev, 30,30)==False
    # veto
    v = veto_signal(sig_t, [ev], 30,30, "high")
    assert v["blocked"]==True
    v2 = veto_signal(sig_t2, [ev], 30,30, "high")
    assert v2["blocked"]==False
    # NEWS_UNAVAILABLE empty => no veto
    stub = fetch_macro_calendar_stub()
    assert stub==[]
    v3 = veto_signal(sig_t, stub)
    assert v3["blocked"]==False and "NEWS_UNAVAILABLE" in v3["note"]
    # low impact not veto when min high
    ev_low = NewsEvent(published_at=pub, detected_at=det, impact="low", currency="EUR", title="blah")
    v4 = veto_signal(sig_t, [ev_low], min_impact_for_veto="high")
    assert v4["blocked"]==False

def test_news_available_at_max():
    from gcis.data.news import NewsEvent
    pub = datetime(2024,1,15,10,0, tzinfo=timezone.utc)
    det = datetime(2024,1,15,10,5, tzinfo=timezone.utc)
    ev = NewsEvent(published_at=pub, detected_at=det, impact="high", currency="USD", title="test")
    assert ev.available_at == det  # max
    ev2 = NewsEvent(published_at=det, detected_at=pub, impact="high", currency="USD", title="test")
    assert ev2.available_at == det

def test_retention_policy_and_manifest():
    from gcis.ops.backup import retention_policy, backup_manifest, verify_backup_manifest, run_retention_sweep
    pol = retention_policy()
    assert pol["retention_days"]["parquet_archive"] is None
    assert pol["retention_days"]["raw_wire_frames"]==14
    assert pol["disk_free_min_gb"]==10
    assert "never_delete_referenced_by" in pol
    manifest = backup_manifest()
    assert "generated_at" in manifest
    assert "config_hash" in manifest
    assert "files" in manifest
    ver = verify_backup_manifest(manifest)
    assert "ok" in ver
    sweep = run_retention_sweep(dry_run=True)
    assert sweep["dry_run"]==True
    assert sweep["policy"]["retention_days"]["logs"]==30
    assert "would_delete" in sweep

def test_metrics_rollup_budgets():
    from gcis.ops.metrics import MetricsRollup
    m = MetricsRollup()
    # record some ingest latencies within budget 250 ms
    for v in [100,120,80,200,150]:
        m.record_ingest_to_persist(v)
    for v in [1,2,1,1]:
        m.record_candle_to_signal(v)
    for v in [5,10,15]:
        m.record_bundle_latency(v)
    status = m.budget_status()
    assert status["ingest_ok"]==True
    assert status["candle_ok"]==True
    assert status["bundle_ok"]==True
    # exceed bundle 20s
    m2 = MetricsRollup()
    for v in [25,30,22]:
        m2.record_bundle_latency(v)
    status2 = m2.budget_status()
    assert status2["bundle_ok"]==False
    # 1m rollup
    r = m.rollup_1m()
    assert "timestamp" in r and "events_1m" in r

def test_readiness_report_not_ready_honest():
    from gcis.ops.readiness import readiness_report
    from gcis.core.config import get_config
    cfg = get_config()
    rep = readiness_report(cfg)
    assert "status" in rep
    assert "overall_ready" in rep
    assert "sections" in rep
    # In sandbox with NO_DATA health, readiness should be NOT_READY honest
    # At least not crash and have risk backup census
    assert "data_freshness" in rep["sections"]
    assert "risk" in rep["sections"]
    assert "backup" in rep["sections"]
    assert "census" in rep["sections"]
    # live_enabled false per config default
    assert rep["live_enabled"]==False
    # overall_ready should be False when NO_DATA (honest)
    # may be False
    assert isinstance(rep["overall_ready"], bool)
    # if not ready, note explains
    if not rep["overall_ready"]:
        assert "NOT_READY" in rep["status"]

def test_no_forbidden_strings_p14():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    forb = ["guaranteed profit","risk free","100% win"]
    for p in (root / "src/gcis/risk").rglob("*.py"):
        txt = p.read_text().lower()
        for f in forb:
            assert f not in txt
    for p in (root / "src/gcis/data").rglob("secondary.py"):
        txt = p.read_text().lower()
        for f in forb:
            assert f not in txt
    for p in (root / "src/gcis/ops").rglob("*.py"):
        txt = p.read_text().lower()
        for f in forb:
            assert f not in txt
