"""P22 Last feature: webhook + live final + bundle budget"""
def test_webhook_invalid_and_empty():
    from gcis.ops.webhook import send_webhook, format_alert_payload, healthcheck_webhook
    assert send_webhook("", {"a":1})["ok"]==False
    assert send_webhook("not-http", {"a":1})["reason"]=="invalid_url"
    assert send_webhook("http://example.com", {})["reason"]=="empty_payload"
    p = format_alert_payload("BTCUSDT","BUY", 100.0)
    assert p["symbol"]=="BTCUSDT" and p["source"]=="GCIS-P22"
    hc = healthcheck_webhook("")
    assert hc["ok"]==True and hc["mode"]=="stub"

def test_webhook_network_failover():
    from gcis.ops.webhook import send_webhook
    # unreachable should return network_error not raise
    res = send_webhook("http://127.0.0.1:9/fail", {"ping":1}, timeout=1)
    assert res["ok"]==False
    assert res["reason"] in ("network_error","http_error")

def test_live_final_and_bundle():
    from gcis.execution.live_final import ccxt_live_status, bundle_budget_check
    assert ccxt_live_status("stub")["ok"]==True
    assert ccxt_live_status("live")["ok"]==False
    assert ccxt_live_status("bad")["ok"]==False
    assert bundle_budget_check(15000)["status"]=="PASS"
    assert bundle_budget_check(25000)["status"]=="FAIL"

def test_no_forbidden_p22():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    forb=["guaranteed profit","risk free","100% win"]
    for p in (root / "src/gcis/ops/webhook.py").read_text().lower(), (root / "src/gcis/execution/live_final.py").read_text().lower():
        assert all(f not in p for f in forb)
