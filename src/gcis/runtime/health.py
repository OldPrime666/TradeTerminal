from datetime import datetime, timezone, timedelta
from gcis.persistence.db import get_session
from gcis.persistence.models import SystemHealth, WorkerState, ProviderStatus, Candle, DailyRiskState, KillSwitchState
from sqlalchemy import func


def _transport_status_from_workers(workers: dict, worker_rows: list) -> str:
    """
    Derive truthful transport status from WorkerState.
    Expected states from TransportManager: WEBSOCKET / DEGRADED / DISCONNECTED / FAILED / HEALTHY.
    HEALTHY is legacy -> treat as WEBSOCKET if not stale.
    If no worker row -> NO DATA.
    Stale heartbeat >120s => DISCONNECTED (process dead).
    """
    # priority: transport, ingest, data, stream
    for key in ("transport", "ingest", "data", "stream"):
        if key in workers:
            state = workers[key]
            # check staleness
            row = next((w for w in worker_rows if w.process == key), None)
            if row and row.last_heartbeat:
                hb = row.last_heartbeat
                if hb.tzinfo is None:
                    hb = hb.replace(tzinfo=timezone.utc)
                age_s = (datetime.now(timezone.utc) - hb).total_seconds()
                if age_s > 120:
                    return "DISCONNECTED"
                if age_s > 60 and state == "WEBSOCKET":
                    return "DEGRADED"
            # normalize
            if state in ("WEBSOCKET", "DEGRADED", "DISCONNECTED"):
                return state
            if state == "FAILED":
                return "DISCONNECTED"
            if state == "HEALTHY":
                return "WEBSOCKET"
            return state
    return "NO DATA"


def compute_health() -> dict:
    db = get_session()
    try:
        # DB reachability
        db_ok = True
        try:
            # cheap reachability — query Candle table (works on sqlite)
            db.query(Candle).limit(1).all()
        except Exception:
            db_ok = False
        # provider statuses — full detail
        providers = db.query(ProviderStatus).all()
        provider_map = {p.provider: p.status for p in providers}
        provider_details = [
            {
                "provider": p.provider,
                "venue": p.venue,
                "capability": p.capability,
                "status": p.status,
                "role": p.role,
                "last_success": p.last_success.isoformat() if p.last_success else None,
                "last_failure": p.last_failure.isoformat() if p.last_failure else None,
                "latency_ms": p.latency_ms,
                "data_age_s": p.data_age_s,
                "circuit_state": p.circuit_state,
            }
            for p in providers
        ]
        # worker states — full detail
        workers = db.query(WorkerState).all()
        workers_map = {w.process: w.state for w in workers}
        worker_details = [
            {
                "process": w.process,
                "pid": w.pid,
                "state": w.state,
                "last_heartbeat": w.last_heartbeat.isoformat() if w.last_heartbeat else None,
                "lag_ms": w.lag_ms,
                "queue_depth": w.queue_depth,
                "last_error": (w.last_error[:200] if w.last_error else None),
            }
            for w in workers
        ]
        # transport truth: WorkerState primary; fallback infer from ProviderStatus if no worker yet.
        transport_status = _transport_status_from_workers(workers_map, workers)
        if transport_status == "NO DATA" and providers:
            # infer from provider health if transport not yet started but preflight did REST
            healthy_caps = [p for p in providers if p.status == "HEALTHY"]
            live_quote_healthy = any("live_quote" in (p.capability or "") and p.status == "HEALTHY" for p in providers)
            if live_quote_healthy:
                transport_status = "WEBSOCKET"
            elif healthy_caps:
                transport_status = "DEGRADED"
            else:
                transport_status = "DISCONNECTED"
        # candle freshness
        last_candle = db.query(Candle).order_by(Candle.close_time.desc()).first()
        freshness = "UNKNOWN"
        if last_candle:
            ct = last_candle.close_time
            if ct is not None and ct.tzinfo is None:
                ct = ct.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - ct).total_seconds() if ct else 999999
            if age < 600:
                freshness = "HEALTHY"
            elif age < 1800:
                freshness = "DEGRADED"
            else:
                freshness = "STALE"
        else:
            freshness = "NO DATA"

        # risk status truth: DailyRiskState + KillSwitchState (persistence truth, not computed)
        try:
            dr = db.query(DailyRiskState).order_by(DailyRiskState.risk_day.desc()).first()
            ks = db.query(KillSwitchState).order_by(KillSwitchState.id.desc()).first()
            risk_status = {
                "risk_lock": dr.risk_lock if dr else "UNKNOWN",
                "trades_today": dr.trades_today if dr else None,
                "daily_realized_pnl": str(dr.daily_realized_pnl) if dr and dr.daily_realized_pnl is not None else None,
                "kill_active": bool(ks.active) if ks else False,
                "kill_mode": ks.mode if ks else None,
                "kill_reason": ks.reason if ks else None,
            }
        except Exception:
            risk_status = {"risk_lock": "UNKNOWN", "kill_active": False}

        # verdict: DB must be ok; then transport + freshness + risk lock + kill + failed workers
        if not db_ok:
            verdict = "UNHEALTHY"
        elif risk_status.get("kill_active"):
            verdict = "DEGRADED"
        elif transport_status == "DISCONNECTED" or freshness in ("STALE", "NO DATA"):
            verdict = "DEGRADED"
        elif any(w.state == "FAILED" for w in workers):
            verdict = "DEGRADED"
        elif transport_status == "DEGRADED" or freshness == "DEGRADED":
            verdict = "DEGRADED"
        else:
            verdict = "HEALTHY"

        details = {
            "db_ok": db_ok,
            "providers": provider_map,
            "provider_details": provider_details,
            "workers": workers_map,
            "worker_details": worker_details,
            "transport_status": transport_status,
            "candle_freshness": freshness,
            "last_candle_time": last_candle.close_time.isoformat() if last_candle else None,
            "risk_status": risk_status,
        }
        # persist
        h = SystemHealth(verdict=verdict, details=details, checked_at=datetime.now(timezone.utc))
        db.add(h)
        db.commit()
        return {"verdict": verdict, "details": details}
    finally:
        db.close()


def update_worker_heartbeat(process: str, pid: int, state: str = "HEALTHY", error: str | None = None, queue_depth: int | None = None, lag_ms: int | None = None):
    db = get_session()
    try:
        w = db.query(WorkerState).filter(WorkerState.process == process).first()
        now = datetime.now(timezone.utc)
        if not w:
            w = WorkerState(process=process, pid=pid, started_at=now, last_heartbeat=now, state=state, last_error=error, queue_depth=queue_depth, lag_ms=lag_ms)
            db.add(w)
        else:
            w.pid = pid
            w.last_heartbeat = now
            w.state = state
            w.last_error = error
            if queue_depth is not None:
                w.queue_depth = queue_depth
            if lag_ms is not None:
                w.lag_ms = lag_ms
        db.commit()
    finally:
        db.close()
