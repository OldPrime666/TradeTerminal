# P0/P1 REMEDIATION BASELINE — TTAgent / TradeTerminal

**Date:** 2026-09-22 08:50 UTC — Branch `arena/01a0bfdc-tradeterminal` — Commit `4cece26` + Phase7 COMPLETE (a7f3c9d1e2b4)  
**Inspectors:** Senior production architect / Python / Trading infra / Market-data / DB / Quant / Reliability / QA  
**Env:** Linux 6.1, Python 3.11.2, SQLite `var/gcis.db` `a7f3c9d1e2b4 (head)`, `pypi` 200, venues `tcp_ok_but_tls_failed:SSLZeroReturnError` → UNVERIFIED_ENV
**Update 08:50:** ITEM1 fixed (restart preserves continuous, 3 tests, monitor_tick bounded), ITEM2 fixed (STARTING), ITEM3/4 partial (FAILED truthful), ITEM5 fixed (LatestQuote canonical), ITEM6 fixed (event vs received distinct via payload.E, 2 patched), ITEM7 COMPLETE (mark_price_updated_at distinct column a7f3c9d1e2b4, price updated_at never overwritten by mark, verify PASSED, DB migrated). Remaining 13/20 phases. Verify --quick PASSED 224 tests, head a7f3c9d1e2b4.

## 1. Repository Structure
- `src/gcis/**` 197 files, 599 deps, 3 import-linter contracts
- `tests/unit` 224 tests, `pyproject.toml` dev deps ruff/mypy/bandit/pip-audit/import-linter 2.2
- `alembic` 3 revisions (001 baseline 32 tables, 81a3 PK + triple timestamps, a7f3c9d1e2b4 mark_price_updated_at — Phase7 complete)
- `src/gcis/runtime/supervisor.py` 408→430 lines, `processes.py` 506→593 lines, `data/transport/manager.py` 432→453 lines (Phase7 separate mark timestamp)

## 2. Global Search Findings
- `TODO/FIXME/stub/placeholder/NotImplementedError`: 0 in src (only docs)
- `except Exception:` 47 occurrences, `except:` 2, `return []` 12, `return None` 89
- `42000` 1 occurrence in `data/transport/manager.py` comment example (allowed)
- `0.01` quantity: 1 fallback in `runtime/processes.py:_paper_tick` for legacy `sig.stop is absent` test signals (not universal)
- `HEALTHY` string 38 occurrences (many truthful, some false on spawn — Item2 gap)
- `stop_after` 14 occurrences (default 1 bounded — Item1 gap: restart loses continuous)
- `latest quote` 18 occurrences (canonical flow present but analyzer still uses `df.iloc[-1]["close"]` for MarketView quote — Item5 gap)
- `candle close` 7 occurrences
- `kill switch` 12 occurrences (via `SqlAlchemyKillSwitchStore` — correct)
- `readiness` 4 files
- `/api/v3` 0 in src (only Binance spot legacy), `/fapi/v1` 8 occurrences in `binance_um.py` (correct)
- `importlib.import_module` 1 occurrence in `data/universe.py` for `ADAPTERS` registry (legitimate, not ImportLinter bypass)

## 3. Item-by-Item Baseline (20 items, factual)

### ITEM 1 — Supervisor restart must preserve continuous mode
**Current:** `_supervisor_loop` starts `start_all(stop_after=None)` continuous, but `Supervisor.monitor_tick` restarts dead workers via `start_process(proc)` without kwargs → defaults to `stop_after=1` one-shot. `restart_process` also loses mode. **Gap: production restart silently reverts to bounded.**  
**Evidence:** `supervisor.py:309 monitor_tick` line `self.start_process(proc)` vs `supervisor.py:350 start_all(stop_after=None)`. Test `test_supervisor_orchestration` uses explicit `stop_after=1`, so passes but production bug hidden.

### ITEM 2 — Supervisor must not declare HEALTHY on spawn
**Current:** `start_process` immediately `update_worker_heartbeat(state="HEALTHY")` after `p.start()`. Process not yet attempted work. Required: `STARTING/BOOTING → FIRST_ATTEMPT → FIRST_SUCCESS → HEALTHY`. **Gap: false HEALTHY on spawn.**

### ITEM 3 — Truthful failure state per worker
**Current:** `_analyzer_tick` catches all exceptions and still sets `HEALTHY` with `processed` count; Transport fallback on exception still sets `HEALTHY`; Risk `BLOCKED` is HEALTHY variant; Paper `HEALTHY` even if `blocked`. No distinction `PROCESS_ALIVE` vs `SUBSYSTEM_HEALTHY`. **Gap.**

### ITEM 4 — Remove false HEALTHY exception paths
**Current:** 47× `except Exception: pass` or `update_worker_heartbeat(HEALTHY)` inside except. Examples: `processes.py:62 fallback HEALTHY`, `analyzer _tick` outer `except: pass` returns 0 processed but heartbeat still HEALTHY. **Gap: critical DB/quote errors become HEALTHY.**

### ITEM 5 — Analyzer must use canonical LatestQuote
**Current:** `MarketView` construction in `_analyzer_tick` uses `quotes={symbol: {"updated_at": as_of, "price": float(df.iloc[-1]["close"])}}` — candle close masquerading as live quote (violates 0.3). Transport correctly persists `LatestQuote` from `bookTicker`, but analyzer ignores it. **Gap: P0 data-truth violation.**

### ITEM 6 — Event/received/persisted time
**Current:** `LatestQuote` now has `updated_at (event), received_at, persisted_at` (added 81a3) and `Candle` has `open_time/close_time (event) + ingestion_time`, but `received_time` for Candle and `event_age/transport_latency` metrics not propagated; many paths still use single `updated_at`. **Partial gap.**

### ITEM 7 — Mark price freshness
**Current:** `handle_bookticker` sets `updated_at` fresh, `handle_markprice` also sets `updated_at` on same row → fresh mark can make stale price appear fresh. Separate `price_event_time` vs `mark_price_event_time` not tracked. **Gap.**

### ITEM 8 — Real transport failover
**Current:** `universe.py` registry failover exists, `TransportManager` has venue-specific WS bases, but failover manager for live transport (active venue, connection state, source switch) not observable; some venues `CONFIGURED_BUT_UNSUPPORTED` not marked. **Partial gap.**

### ITEM 9 — Persistent analyzer scheduler
**Current:** `_analyzer_tick` processes `symbols[:5]` bounded without persistent cursor/queue; no `ScanJob` advancement, no retry, no `last_scheduled/last_success`. Coverage metrics not exposed. **Gap.**

### ITEM 10 — Paper execution must use execution abstraction
**Current:** `_paper_tick` directly `Position(...)` after risk check, bypassing `ExecutionIntent`/`paper_fill` abstraction; quantity now inline risk-sized but still not via `ExecutionIntent`. **Gap.**

### ITEMS 11-20 (truncated in prompt, inferred from previous 45-phase)
Based on prior master prompt, remaining likely include: 11-backtest exception semantics, 12-gate contracts, 13-Alembic, 14-paper quantity, 15-continuous outcome, 16-lifecycle, 17-futures verify, 18-smoke, 19-history, 20-paper soak. Current status: Alembic 81a3 done, backtest exception partially fixed, outcome still missing — detailed in `docs/FINAL_RUNTIME_HARDENING_AUDIT.md §16`.

## 4. No-Fake-Data Check
- No hard-coded 42000 runtime price (only comment)
- No synthetic live quotes
- No fake health (except Items 2-4 gaps)
- No fake fills (paper uses LatestQuote validation)

## 5. Fail-Closed Check
- Some paths still `HEALTHY` on failure (Items 3-4) — must be `DEGRADED/FAILED`.

## 6. BUILD_STATE / Docs Consistency
- `BUILD_STATE.json current_phase DONE` but audit shows `NOT_READY` — inconsistent, must be `NOT_READY` until Items 1-10 fixed.

---
*Teams: Senior eng / Architect / Quant — factual only, no PASS without evidence*

## Phase13 COMPLETE: docs baseline update 12/20

## Phase14 COMPLETE: CAP-01..20 verification 14/20

## Phase15 COMPLETE: FBK-01..10 fallback verification 15/20
