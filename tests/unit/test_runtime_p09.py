"""P09 runtime tests: supervisor 4 processes, heartbeats ≤5s, backoff jitter, crash-loop, recovery, commands."""
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

def test_heartbeat_le_5s(monkeypatch, tmp_path):
    from gcis.persistence.db import Base, get_engine
    from sqlalchemy.orm import sessionmaker
    from gcis.persistence.models import WorkerState
    db_url = f"sqlite:///{tmp_path}/test_heartbeat.db"
    engine = get_engine(db_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    monkeypatch.setattr("gcis.persistence.db.get_session", lambda: SessionLocal())
    monkeypatch.setattr("gcis.runtime.health.get_session", lambda: SessionLocal())
    monkeypatch.setattr("gcis.runtime.supervisor.get_session", lambda: SessionLocal())
    from gcis.runtime.health import update_worker_heartbeat
    from gcis.runtime.supervisor import should_heartbeat_be_fresh, heartbeat_age_ms
    update_worker_heartbeat("transport", pid=123, state="HEALTHY")
    s = SessionLocal()
    w = s.query(WorkerState).filter(WorkerState.process=="transport").first()
    assert w is not None
    assert should_heartbeat_be_fresh(w.last_heartbeat, datetime.now(timezone.utc), 5) is True
    old = datetime.now(timezone.utc) - timedelta(seconds=6)
    w.last_heartbeat = old
    s.commit()
    assert should_heartbeat_be_fresh(w.last_heartbeat, datetime.now(timezone.utc), 5) is False
    assert heartbeat_age_ms(w.last_heartbeat) > 5000
    s.close()

def test_backoff_schedule_jitter():
    from gcis.runtime.supervisor import next_backoff, BACKOFF_SCHEDULE
    assert BACKOFF_SCHEDULE == [1,2,4,8,16,30,60]
    b0 = next_backoff(0, jitter=False)
    assert b0 == 1
    bj = next_backoff(0, jitter=True)
    assert 0.8 <= bj <= 1.2
    assert next_backoff(10, jitter=False) == 60
    assert 48 <= next_backoff(10, jitter=True) <= 72

def test_crash_loop_breaker():
    from gcis.runtime.supervisor import is_crash_loop
    now = datetime.now(timezone.utc)
    failures = [now - timedelta(minutes=i) for i in range(5)]
    assert is_crash_loop(failures, now, window_minutes=10, threshold=5) is False
    failures6 = [now - timedelta(minutes=i) for i in range(6)]
    assert is_crash_loop(failures6, now, window_minutes=10, threshold=5) is True
    old_failures = [now - timedelta(minutes=11+i) for i in range(5)] + [now]
    assert is_crash_loop(old_failures, now) is False

def test_recovery_idempotency(monkeypatch, tmp_path):
    from gcis.persistence.db import Base, get_engine
    from sqlalchemy.orm import sessionmaker
    from gcis.persistence.models import WorkerState
    db_url = f"sqlite:///{tmp_path}/test_recovery.db"
    engine = get_engine(db_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    monkeypatch.setattr("gcis.persistence.db.get_session", lambda: SessionLocal())
    monkeypatch.setattr("gcis.runtime.health.get_session", lambda: SessionLocal())
    monkeypatch.setattr("gcis.runtime.supervisor.get_session", lambda: SessionLocal())
    from gcis.runtime.supervisor import Supervisor
    sup = Supervisor()
    assert sup.recover_idempotent("transport") is True
    s = SessionLocal()
    w = s.query(WorkerState).filter(WorkerState.process=="transport").first()
    assert w.state == "HEALTHY"
    s.close()
    assert sup.recover_idempotent("transport") is True
    s2 = SessionLocal()
    assert s2.query(WorkerState).filter(WorkerState.process=="transport").count() == 1
    s2.close()

def test_command_idempotency(monkeypatch, tmp_path):
    from gcis.persistence.db import Base, get_engine
    from sqlalchemy.orm import sessionmaker
    db_url = f"sqlite:///{tmp_path}/test_cmd.db"
    engine = get_engine(db_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    monkeypatch.setattr("gcis.persistence.db.get_session", lambda: SessionLocal())
    monkeypatch.setattr("gcis.runtime.health.get_session", lambda: SessionLocal())
    monkeypatch.setattr("gcis.runtime.supervisor.get_session", lambda: SessionLocal())
    from gcis.runtime.supervisor import Supervisor
    sup = Supervisor()
    res1 = sup.handle_command(idempotency_key="key-123", cmd_type="KILL_SWITCH", payload={"mode":"BLOCK_NEW_TRADES"})
    assert res1["idempotent"] is False
    assert res1["status"] == "SUCCESS"
    cid1 = res1["command_id"]
    res2 = sup.handle_command(idempotency_key="key-123", cmd_type="KILL_SWITCH", payload={"mode":"BLOCK_NEW_TRADES"})
    assert res2["idempotent"] is True
    assert res2["command_id"] == cid1
    res3 = sup.handle_command(idempotency_key="key-456", cmd_type="KILL_SWITCH", payload={"mode":"BLOCK_NEW_TRADES"})
    assert res3["command_id"] != cid1
    assert res3["idempotent"] is False

def test_supervisor_4_processes_and_heartbeat_check(monkeypatch, tmp_path):
    from gcis.persistence.db import Base, get_engine
    from sqlalchemy.orm import sessionmaker
    from gcis.persistence.models import WorkerState
    db_url = f"sqlite:///{tmp_path}/test_4proc.db"
    engine = get_engine(db_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    monkeypatch.setattr("gcis.persistence.db.get_session", lambda: SessionLocal())
    monkeypatch.setattr("gcis.runtime.health.get_session", lambda: SessionLocal())
    monkeypatch.setattr("gcis.runtime.supervisor.get_session", lambda: SessionLocal())
    from gcis.runtime.supervisor import Supervisor, PROCESSES
    from gcis.runtime.health import update_worker_heartbeat
    assert len(PROCESSES) == 4
    assert set(PROCESSES) == {"transport","analyzer","risk","paper"}
    sup = Supervisor()
    for p in PROCESSES:
        update_worker_heartbeat(p, pid=100+hash(p)%1000, state="HEALTHY")
    statuses = sup.check_heartbeats()
    for p in PROCESSES:
        assert statuses[p] == "HEALTHY"
    s = SessionLocal()
    w = s.query(WorkerState).filter(WorkerState.process=="transport").first()
    w.last_heartbeat = datetime.now(timezone.utc) - timedelta(seconds=10)
    s.commit()
    s.close()
    statuses2 = sup.check_heartbeats()
    assert statuses2["transport"] == "DEGRADED"
    s2 = SessionLocal()
    w2 = s2.query(WorkerState).filter(WorkerState.process=="transport").first()
    w2.last_heartbeat = datetime.now(timezone.utc) - timedelta(seconds=40)
    s2.commit()
    s2.close()
    statuses3 = sup.check_heartbeats()
    assert statuses3["transport"] == "DISCONNECTED"

def test_supervisor_processes_exist():
    from gcis.runtime.processes import PROCESSES, run_transport, run_analyzer, run_risk, run_paper
    assert "transport" in PROCESSES
    assert "analyzer" in PROCESSES
    assert "risk" in PROCESSES
    assert "paper" in PROCESSES
    assert callable(run_transport)
    assert callable(run_analyzer)
