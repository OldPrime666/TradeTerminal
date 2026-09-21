from datetime import datetime, timezone
from gcis.persistence.db import get_session
from gcis.persistence.models import SystemHealth, WorkerState, ProviderStatus, Candle
from sqlalchemy import func

def compute_health() -> dict:
    db = get_session()
    try:
        # DB reachability
        db_ok = True
        try:
            db.execute(func.now() if hasattr(func,'now') else "SELECT 1")
            # try simple query
            db.query(Candle).limit(1).all()
        except Exception as e:
            db_ok = False
        # provider statuses
        providers = db.query(ProviderStatus).all()
        provider_map = {p.provider: p.status for p in providers}
        # worker states
        workers = db.query(WorkerState).all()
        # candle freshness
        # last candle time
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

        # verdict
        if not db_ok:
            verdict = "UNHEALTHY"
        elif freshness in ("STALE","NO DATA"):
            verdict = "DEGRADED"
        elif any(w.state=="FAILED" for w in workers):
            verdict = "DEGRADED"
        else:
            verdict = "HEALTHY"

        details = {
            "db_ok": db_ok,
            "providers": provider_map,
            "workers": {w.process: w.state for w in workers},
            "candle_freshness": freshness,
            "last_candle_time": last_candle.close_time.isoformat() if last_candle else None,
        }
        # persist
        h = SystemHealth(verdict=verdict, details=details, checked_at=datetime.now(timezone.utc))
        db.add(h)
        db.commit()
        return {"verdict": verdict, "details": details}
    finally:
        db.close()

def update_worker_heartbeat(process: str, pid: int, state: str = "HEALTHY", error: str | None = None, queue_depth: int | None = None, lag_ms: int | None = None):
    from datetime import datetime, timezone
    db = get_session()
    try:
        w = db.query(WorkerState).filter(WorkerState.process==process).first()
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
