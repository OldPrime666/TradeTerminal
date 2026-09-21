"""P07 Supervisor orchestration — real Process spawn/terminate, PID tracking, crash-loop, no orphan, Windows spawn."""
import time
from datetime import datetime, timezone, timedelta

def _setup_isolated_db(monkeypatch, tmp_path):
    from gcis.persistence.db import Base, get_engine
    from sqlalchemy.orm import sessionmaker
    db_url = f"sqlite:///{tmp_path}/sup_orch.db"
    engine = get_engine(db_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    monkeypatch.setattr("gcis.persistence.db.get_session", lambda: SessionLocal())
    monkeypatch.setattr("gcis.runtime.health.get_session", lambda: SessionLocal())
    monkeypatch.setattr("gcis.runtime.supervisor.get_session", lambda: SessionLocal())
    return SessionLocal

def _slow_analyzer_for_test(stop_after=10):
    import time
    from gcis.runtime.health import update_worker_heartbeat
    import os
    for _ in range(stop_after):
        update_worker_heartbeat("analyzer", pid=os.getpid(), state="HEALTHY")
        time.sleep(0.2)
    return "done"

def test_supervisor_start_stop_single(monkeypatch, tmp_path):
    SessionLocal = _setup_isolated_db(monkeypatch, tmp_path)
    from gcis.runtime.supervisor import Supervisor
    sup = Supervisor()
    # start transport with small stub (stop_after=1) — should spawn real Process and then exit quickly
    res = sup.start_process("transport", stop_after=1)
    assert res["ok"] is True
    assert res["status"] in ("STARTED", "ALREADY_RUNNING")
    pid = res.get("pid")
    assert isinstance(pid, int)
    # give process time to start and finish (wired transport does DB + heartbeat, ~0.3s)
    time.sleep(1.0)
    # is_alive should be False after stub finishes (it exits after stop_after cycles)
    # But we still have tracking; after exit, is_alive false
    # Poll briefly if still alive due to slow spawn
    for _ in range(5):
        if not sup.is_alive("transport"):
            break
        time.sleep(0.2)
    assert sup.is_alive("transport") is False
    # stop should be no-op or stopped
    stop_res = sup.stop_process("transport")
    assert stop_res["ok"] is True
    # no orphan
    assert "transport" not in sup._procs

def test_supervisor_no_duplicate_ownership(monkeypatch, tmp_path):
    SessionLocal = _setup_isolated_db(monkeypatch, tmp_path)
    from gcis.runtime.supervisor import Supervisor
    sup = Supervisor()
    # start a longer-lived dummy: we use analyzer with stop_after=10 (longer than test sleep)
    # but we patch target to a slow function to keep alive — must be picklable (module-level)
    import gcis.runtime.processes as proc_mod
    orig = proc_mod.run_analyzer
    monkeypatch.setattr(proc_mod, "run_analyzer", _slow_analyzer_for_test)
    # need to refresh target resolution inside supervisor (it imports lazily each time)
    res1 = sup.start_process("analyzer", stop_after=10)
    assert res1["ok"] is True
    pid1 = res1["pid"]
    # second start should be ALREADY_RUNNING, not duplicate
    res2 = sup.start_process("analyzer", stop_after=10)
    assert res2["status"] == "ALREADY_RUNNING"
    assert res2["pid"] == pid1
    assert len([p for p in sup._procs.values() if p.is_alive()]) == 1
    # cleanup
    time.sleep(0.3)
    sup.stop_process("analyzer", timeout=2)
    monkeypatch.setattr(proc_mod, "run_analyzer", orig)
    assert sup.is_alive("analyzer") is False

def test_supervisor_crash_loop_breaker(monkeypatch, tmp_path):
    SessionLocal = _setup_isolated_db(monkeypatch, tmp_path)
    from gcis.runtime.supervisor import Supervisor, CRASH_LOOP_THRESHOLD
    sup = Supervisor()
    # simulate 6 failures within 10m
    for _ in range(CRASH_LOOP_THRESHOLD + 1):
        sup.record_failure("paper", error="crash")
    # now start should be blocked by crash-loop breaker
    res = sup.start_process("paper", stop_after=1)
    assert res["ok"] is False
    assert res["status"] == "FAILED"
    assert res["reason"] == "crash_loop"

def test_supervisor_start_all_stop_all(monkeypatch, tmp_path):
    SessionLocal = _setup_isolated_db(monkeypatch, tmp_path)
    from gcis.runtime.supervisor import Supervisor
    sup = Supervisor()
    results = sup.start_all(stop_after=1)
    assert set(results.keys()) == {"transport", "analyzer", "risk", "paper"}
    for proc, r in results.items():
        assert r["ok"] is True
    time.sleep(0.8)
    stop_results = sup.stop_all(timeout=2)
    for proc, r in stop_results.items():
        assert r["ok"] is True
    # no orphans
    assert len(sup._procs) == 0
    # no duplicate after restart
    for proc in ["transport", "analyzer"]:
        assert sup.is_alive(proc) is False

def test_supervisor_monitor_tick_detects_dead(monkeypatch, tmp_path):
    SessionLocal = _setup_isolated_db(monkeypatch, tmp_path)
    from gcis.runtime.supervisor import Supervisor
    from gcis.runtime.health import update_worker_heartbeat
    sup = Supervisor()
    # fake a heartbeat HEALTHY but no process alive
    update_worker_heartbeat("transport", pid=99999, state="HEALTHY")
    # ensure no proc
    assert sup.is_alive("transport") is False
    actions = sup.monitor_tick()
    # should attempt restart (or mark failed if crash-loop)
    assert actions["transport"] in ("RESTARTED_DEAD", "FAILED_CRASH_LOOP", "NOT_RUNNING")
