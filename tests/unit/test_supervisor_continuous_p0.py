"""ITEM 1 — Supervisor restart must preserve continuous worker mode (P0)"""

import time
from datetime import datetime, timezone

def _setup_db(monkeypatch, tmp_path):
    from gcis.persistence.db import Base, get_engine
    from sqlalchemy.orm import sessionmaker
    # ensure models registered before create_all
    import gcis.persistence.models  # noqa: F401
    db_url = f"sqlite:///{tmp_path}/sup_cont.db"
    engine = get_engine(db_url)
    Base.metadata.create_all(bind=engine)
    # keep original SessionLocal for parent queries (same engine) — fork-safe for child via _new_session? use same engine but child inherits forked engine which is okay for short-lived? Use _new_session for health/supervisor
    SessionLocal = sessionmaker(bind=engine)
    def _new_session():
        eng = get_engine(db_url)
        return sessionmaker(bind=eng)()
    # parent and child both use SessionLocal that is bound to engine with file; but child after fork reuses parent engine memory — we patch health/supervisor to use _new_session (fresh engine) for child safety
    monkeypatch.setattr("gcis.persistence.db.get_session", _new_session)
    monkeypatch.setattr("gcis.runtime.health.get_session", _new_session)
    monkeypatch.setattr("gcis.runtime.supervisor.get_session", _new_session)
    # also ensure direct queries via SessionLocal see same DB file — SessionLocal uses original engine, but file same, so ok
    # For test direct queries, use _new_session as well to see child's writes
    return _new_session

def _dummy_continuous(stop_after=None):
    import time, os
    from gcis.runtime.health import update_worker_heartbeat
    # continuous if stop_after is None -> loop long enough for test, then exit if not killed
    # first heartbeat delayed to let supervisor STARTING be observable
    if stop_after is None:
        try:
            time.sleep(0.4)
            for _ in range(50):
                update_worker_heartbeat("transport", pid=os.getpid(), state="HEALTHY")
                time.sleep(0.1)
        except KeyboardInterrupt:
            return
    else:
        for _ in range(stop_after):
            update_worker_heartbeat("transport", pid=os.getpid(), state="HEALTHY")
            time.sleep(0.05)

def test_restart_preserves_continuous(monkeypatch, tmp_path):
    SessionLocal = _setup_db(monkeypatch, tmp_path)
    from gcis.runtime.supervisor import Supervisor
    import gcis.runtime.processes as proc_mod
    orig = proc_mod.run_transport
    orig_map = proc_mod.PROCESSES.get("transport")
    monkeypatch.setattr(proc_mod, "run_transport", _dummy_continuous)
    monkeypatch.setitem(proc_mod.PROCESSES, "transport", _dummy_continuous)
    sup = Supervisor()
    # start continuous (production mode)
    res = sup.start_process("transport", stop_after=None)
    assert res["ok"] and res["mode"] == "continuous"
    assert sup._last_kwargs["transport"].get("stop_after") is None
    time.sleep(0.3)
    assert sup.is_alive("transport") is True
    # simulate crash: kill process
    sup._procs["transport"].terminate()
    sup._procs["transport"].join(timeout=2)
    assert sup.is_alive("transport") is False
    # record failure and restart via monitor_tick should preserve continuous
    sup.record_failure("transport", error="simulated crash")
    # monitor_tick will detect dead but heartbeat HEALTHY -> restart
    from gcis.runtime.health import update_worker_heartbeat
    update_worker_heartbeat("transport", pid=9999, state="HEALTHY")
    actions = sup.monitor_tick()
    # should have restarted
    assert sup.is_alive("transport") is True
    # check restarted mode is continuous
    assert sup._last_kwargs["transport"].get("stop_after") is None
    # restart count increments
    assert sup.attempts["transport"] >= 1
    sup.stop_all(timeout=2)
    monkeypatch.setattr(proc_mod, "run_transport", orig)
    monkeypatch.setitem(proc_mod.PROCESSES, "transport", orig_map)

def test_starting_not_healthy_on_spawn(monkeypatch, tmp_path):
    SessionLocal = _setup_db(monkeypatch, tmp_path)
    from gcis.runtime.supervisor import Supervisor
    import gcis.runtime.processes as proc_mod
    orig = proc_mod.run_transport
    orig_map = proc_mod.PROCESSES.get("transport")
    monkeypatch.setattr(proc_mod, "run_transport", _dummy_continuous)
    monkeypatch.setitem(proc_mod.PROCESSES, "transport", _dummy_continuous)
    sup = Supervisor()
    res = sup.start_process("transport", stop_after=None)
    # immediately after spawn, DB should be STARTING not HEALTHY (ITEM 2)
    from gcis.persistence.models import WorkerState
    s = SessionLocal()
    w = s.query(WorkerState).filter(WorkerState.process=="transport").first()
    assert w is not None
    assert w.state == "STARTING"
    s.close()
    # after worker heartbeat, it becomes HEALTHY
    time.sleep(0.4)
    s = SessionLocal()
    w = s.query(WorkerState).filter(WorkerState.process=="transport").first()
    assert w.state == "HEALTHY"
    s.close()
    sup.stop_all(timeout=2)
    monkeypatch.setattr(proc_mod, "run_transport", orig)
    monkeypatch.setitem(proc_mod.PROCESSES, "transport", orig_map)

def test_backoff_and_crash_loop(monkeypatch, tmp_path):
    SessionLocal = _setup_db(monkeypatch, tmp_path)
    from gcis.runtime.supervisor import Supervisor, CRASH_LOOP_THRESHOLD
    sup = Supervisor()
    for _ in range(CRASH_LOOP_THRESHOLD+1):
        sup.record_failure("paper", error="x")
    res = sup.start_process("paper", stop_after=1)
    assert res["ok"] is False and res["reason"]=="crash_loop"
