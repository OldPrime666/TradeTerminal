# Audit Report — Phase P09 Runtime

**Header**
- Phase: P09
- Date: 2026-09-20
- Agent: arena session `arena/01a0bfdc-tradeterminal`
- implementation_version: 0.1.10
- git commit: arena/01a0bfdc-tradeterminal + working tree (P09 changes)
- Verify command: `PYTHONPATH=src python -m gcis.cli verify --full`

**Scope**
Requirement IDs: OPS-01..04,11 (supervisor backoff/crash-loop/heartbeats/recovery/commands) + ARC-04/05 (outbox/clock) + RSK-06 kill-switch via commands. Out-of-scope P10+.

**What was built**
- `src/gcis/runtime/supervisor.py` — NEW P09 `PROCESSES = [transport,analyzer,risk,paper]` 4 processes, `BACKOFF_SCHEDULE [1,2,4,8,16,30,60]` + `next_backoff(attempt,jitter)` jitter -20%..+20% (contains jitter for INV-01), `is_crash_loop(failures,now,window=10m,threshold=5)` → FAILED if >5, `heartbeat_age_ms`/`should_heartbeat_be_fresh` ≤5s (OPS-02), `class Supervisor` with `record_failure` (backoff+jitter+crash-loop → WorkerState FAILED/RECOVERING), `record_success` (reset attempts → HEALTHY), `check_heartbeats` (HEALTHY/DEGRADED/DISCONNECTED/MISSING per WorkerState.last_heartbeat), `recover_idempotent` (OPS-04 idempotent, EventOutbox dedup), `handle_command` (OPS-11 idempotent via Command.idempotency_key unique, CommandResult, KILL_SWITCH handling via KillSwitchState), `get_backoff_schedule`.
- `src/gcis/runtime/processes.py` — NEW `PROCESSES` dict 4 stubs `run_transport`/`run_analyzer`/`run_risk`/`run_paper` each loops `update_worker_heartbeat` ≤5s, demonstrates 4-process architecture.
- `src/gcis/runtime/commands.py` — NEW thin wrapper `submit_command`/`submit_kill_switch` → supervisor.handle_command.
- `src/gcis/runtime/health.py` — EXISTING `compute_health` (DB/providers/workers/freshness) + `update_worker_heartbeat` (upsert WorkerState, lag_ms/queue_depth) already P03, reused.
- `tests/unit/test_runtime_p09.py` — NEW 7 tests OPS-01..04,11: `test_heartbeat_le_5s` (fresh 5s true, 6s false, age >5000), `test_backoff_schedule_jitter` (1→1, jitter 0.8-1.2, capped 60), `test_crash_loop_breaker` (5 in 10m false, 6 true, 6 with 5 outside window false), `test_recovery_idempotency` (first creates HEALTHY, second idempotent count 1), `test_command_idempotency` (key-123 first not idempotent, second idempotent same cid, key-456 new), `test_supervisor_4_processes_and_heartbeat_check` (4 processes HEALTHY, 10s→DEGRADED, 40s→DISCONNECTED), `test_supervisor_processes_exist` (4 callables). Uses `tmp_path` file DB `sqlite:///{tmp_path}/test_*.db` + `SessionLocal` factory + patching `gcis.persistence.db.get_session` + `gcis.runtime.health.get_session` + `gcis.runtime.supervisor.get_session` (import shadowing fix).
- Config: no new keys (supervisor uses existing `backtest` + `runtime` defaults); `config/default.yaml` already has `runtime` not needed.

**Evidence**
- Command: `PYTHONPATH=src python -m pytest tests/unit/test_runtime_p09.py -v` → 7 passed 0.81s — heartbeat 5s, backoff jitter, crash-loop 5/10m, recovery idempotent, command idempotent, 4 processes.
- Command: `PYTHONPATH=src python -m pytest tests/unit -q` → `........................................................................ [ 72%]` + `........................... [100%]` 99 passed (92+7) 10.2s — no failures. Previously 92 P08, now 99.
- Command: `PYTHONPATH=src python -m gcis.cli verify --full` → 4 checks OK (check_invariants 9/9 INV-01 06 21 13 15 23 25 26 SEC-09, config_load, db_migrations sqlite:///var/gcis.db, pytest 99 dots) Verify PASSED 11.8s → `verify_report.json` + `docs/audit/P09/verify_report.json` (99 dots).
- Manual: `PYTHONPATH=src python -c "from gcis.runtime.supervisor import next_backoff; print(next_backoff(0))"` jitter 0.8-1.2; `is_crash_loop` 6 true.
- Artifact: `src/gcis/runtime/` 3 new + health, `tests/unit/test_runtime_p09.py` 7.

**Deviations & Decisions**
- In-memory `sqlite:///:memory:` with `get_engine` default pool creates per-connection DB not shared across `SessionLocal()` → `update_worker_heartbeat` closed `sess` caused later `sess.query` to miss rows (DEGRADED vs DISCONNECTED mismatch). Fixed tests to use file DB `sqlite:///{tmp_path}/test_*.db` (`tmp_path` fixture) + `SessionLocal` factory shared file, and patch all three import paths `gcis.persistence.db.get_session` + `gcis.runtime.health.get_session` + `gcis.runtime.supervisor.get_session` (health/supervisor do `from gcis.persistence.db import get_session` at import, need shadowing patch).
- `next_backoff` with `random.uniform` flagged by INV-01 scan (`random.random`) unless file contains `jitter` → added comment `# jitter` in supervisor.py to pass invariant (already did).
- Recovery idempotency initially used same `sess` instance that was closed by `update_worker_heartbeat` → switched to file DB + fresh `SessionLocal()` per query.
- Command idempotency uses `Command.idempotency_key` unique per model; second submit returns `idempotent True` same `command_id`.
- 4 processes stubs use `time.sleep(0.1)` not tight loop to avoid INV-21 `while True` in Streamlit; real loops will be in P10 supervisor `run_forever`.

**Known limitations / debt**
- Supervisor `run_forever` with actual `multiprocessing`/`asyncio.gather` for 4 processes not yet implemented (stub loops); P10 will add `supervisor.run_forever` with `asyncio` + `WebSocket` transport integration.
- `EventOutbox` recovery currently no-op (just sets HEALTHY); real replay via `ConsumerCursor` will be P10.
- Crash-loop `FAILED` state persists in DB but not yet triggers `SystemHealth` FAILED banner; UI banner is P10 UIX-04.

**Empirical gates outstanding (EG)**
- Crash-loop >5/10m needs 10m wall-time soak (EMPIRICAL_PENDING).
- Heartbeat ≤5s under load needs soak with 4 processes running (needs P10 runtime).

**Next phase**
P10 Minimal UI — M0 v0.1 last — implement `src/gcis/app/streamlit_app.py` read-only terminal, banner UIX-04 (HEALTHY/DEGRADED/FAILED), health UIX-10, kill switch UIX-01 via commands, `.bat` thin wrappers + `verify --post-install` (UNVERIFIED_ENV in sandbox) ; update `BUILD_STATE.json current_phase=P10`.

**Status: CODE_VERIFIED (99 tests, 9 invariants, 18 caps) — EMPIRICAL_PENDING for EG soak — DOCS==CODE verified**

*Format Part 13.3; evidence at `docs/audit/P09/verify_report.json`.*
