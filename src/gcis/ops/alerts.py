"""
OPS-10 alerts — evaluates metrics rollup + readiness + secondary discrepancy + news veto.
Generates alerts with level, dedup, and routes via notifications.
"""
from datetime import datetime, timezone
from typing import List, Dict, Any
from gcis.ops.metrics import get_metrics_rollup
from gcis.ops.readiness import readiness_report
from gcis.ops.notifications import get_notification_manager

ALERT_RULES = {
    "INGEST_LAG": {"metric": "ingest_to_persist_p95_ms", "threshold": 250, "level": "WARN"},
    "BUNDLE_LAG": {"metric": "bundle_latency_p95_s", "threshold": 20, "level": "WARN"},
    "CANDLE_LAG": {"metric": "candle_to_signal_p95_s", "threshold": 3, "level": "WARN"},
    "DATA_DISCREPANCY": {"level": "WARN"},
    "NEWS_BLACKOUT": {"level": "INFO"},
    "READINESS_NOT_READY": {"level": "INFO"},
    "KILL_SWITCH": {"level": "CRITICAL"},
}

def evaluate_alerts(config: dict | None =None, secondary_check: Dict[str,Any] | None =None, news_veto: Dict[str,Any] | None =None) -> List[Dict[str,Any]]:
    alerts: List[Dict[str,Any]] = []
    now = datetime.now(timezone.utc).isoformat()
    # metrics budgets
    rollup = get_metrics_rollup()
    budgets = rollup.budget_status()
    if budgets.get("ingest_to_persist_p95_ms") is not None and budgets["ingest_to_persist_p95_ms"] > 250:
        alerts.append({"alert": "INGEST_LAG", "level": "WARN", "detail": f"ingest p95 {budgets['ingest_to_persist_p95_ms']}ms >250", "timestamp": now})
    if budgets.get("bundle_latency_p95_s") is not None and budgets["bundle_latency_p95_s"] > 20:
        alerts.append({"alert": "BUNDLE_LAG", "level": "WARN", "detail": f"bundle p95 {budgets['bundle_latency_p95_s']}s >20", "timestamp": now, "status": "ANALYSIS_LAG"})
    if budgets.get("candle_to_signal_p95_s") is not None and budgets["candle_to_signal_p95_s"] > 3:
        alerts.append({"alert": "CANDLE_LAG", "level": "WARN", "detail": f"candle_to_signal {budgets['candle_to_signal_p95_s']}s >3", "timestamp": now})
    # readiness
    try:
        readiness = readiness_report(config)
        if not readiness.get("overall_ready"):
            alerts.append({"alert": "READINESS_NOT_READY", "level": "INFO", "detail": f"status {readiness.get('status')} census {readiness.get('sections',{}).get('census',{}).get('verdict')}", "timestamp": now})
        # kill switch
        kill = readiness.get("sections",{}).get("kill_switch",{}).get("active")
        if kill:
            alerts.append({"alert": "KILL_SWITCH_ACTIVE", "level": "CRITICAL", "detail": "kill switch active", "timestamp": now})
    except Exception as e:
        alerts.append({"alert": "READINESS_CHECK_FAILED", "level": "WARN", "detail": str(e), "timestamp": now})
    # secondary discrepancy
    if secondary_check:
        if secondary_check.get("status") in ("WARN","FLAG"):
            lvl = "WARN" if secondary_check["status"]=="WARN" else "WARN"  # flag still warn not critical per spec
            alerts.append({"alert": "MARKET_DATA_DISCREPANCY", "level": lvl, "detail": f"{secondary_check['status']} {secondary_check['bps']}bps", "timestamp": now})
    # news
    if news_veto and news_veto.get("blocked"):
        alerts.append({"alert": "NEWS_BLACKOUT", "level": "INFO", "detail": news_veto.get("reason"), "timestamp": now})
    # dedup by alert name
    seen=set()
    deduped=[]
    for a in alerts:
        if a["alert"] not in seen:
            deduped.append(a)
            seen.add(a["alert"])
    return deduped

def dispatch_alerts(alerts: List[Dict[str,Any]]) -> Dict[str,Any]:
    """
    Dispatch via notifications manager. For P17, just enqueue to log channel.
    Returns dispatched count.
    """
    mgr = get_notification_manager()
    dispatched=0
    for a in alerts:
        mgr.enqueue(a["level"], a["alert"], a["detail"], {"alert": a["alert"]}, channel="log")
        dispatched+=1
    # flush respecting rate limit
    res = mgr.flush()
    return {"dispatched": dispatched, "flush": res, "alerts": alerts}
