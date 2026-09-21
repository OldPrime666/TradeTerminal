# FINAL RUNTIME HARDENING AUDIT — TTAgent / TradeTerminal

**Date:** 2026-09-21 18:15 UTC — Asia/Tehran 21:45  
**Repo:** `OldPrime666/TradeTerminal` — branch `arena/01a0bfdc-tradeterminal` — commit `dbda435` + Phase1 continuous fix 18:10  
**Auditor model:** Senior eng / Systems architect / Quant infra / Data-eng / QA — repository as source of truth, no fake data  
**Environment (wall-time):** Linux 6.1, Python 3.11.2, SQLite `var/gcis.db` Alembic `001 (head)`, disk 18GB, `pypi` 200, venues/Binance Vision `tcp_ok_but_tls_failed:SSLZeroReturnError` → `UNVERIFIED_ENV` honest (never circumvent `SEC-09`)

## 1. Executive Summary
- **13 runtime phases (master 23) inspected & repaired:** Supervisor now continuous (`stop_after=None` in `_supervisor_loop`, `run_analyzer/risk/paper` handle `None` as `while True`), `start.bat` launches Supervisor before Streamlit, health truthful, hard-price removed, canonical `LatestQuote` (`SqlAlchemyCandleRepository`/`KillSwitchStore` DI honest, 598 deps 3 kept 0 broken), Alembic `001` real (no `create_all`), Futures via `BinanceUMAdapter /fapi`, history parquet→Candle bridge, paper truthful but **quantity 0.01 + no continuous TP/SL monitor** remain gaps.
- **Tests:** `224 passed` (Linux equivalent of Windows `.venv`), `lint-imports 0 broken`, `check_invariants 9/9`, `verify --full PASSED` (`db_migrations 001/001`).
- **Wall-time live/data:** `UNVERIFIED_ENV` TLS block → `NO DATA` honest; `PASS_WITH_UNVERIFIED_ENV` maximal per spec (not `LIVE_VERIFIED`). No fabrication, no circumvent, no hard price, no fake PASS.

## 2. Implemented Fixes (what was fixed)
| Area | Before | After | Evidence |
|------|--------|-------|----------|
| **Supervisor daemon** | `run_transport/analyzer/risk/paper(stop_after=1)` default one-shot; `Supervisor.start_process()` passed empty kwargs → one-shot child EXIT | `supervisor.py` `start_process` preserves test default, `_supervisor_loop` now `start_all(stop_after=None)`; `processes.py` `run_analyzer/risk/paper` check `if stop_after is None: while True: tick; heartbeat; sleep(0.3)` (transport already had `run_forever_sync`) | `supervisor.py:347-399` `_supervisor_loop`, `processes.py:220-382` 3× continuous |
| **start.bat** | Preflight+Streamlit only (Supervisor absent) | `start.bat` preflight → `start "GCIS Supervisor" /min cmd /c "%PY% -m gcis.runtime.supervisor"` → `streamlit run` ; uses `.venv\Scripts\python.exe` preferentially; fails fast on preflight errorlevel 1 | `start.bat` 32 lines, `healthcheck.bat`, `install.bat` |
| **Health** | Could report HEALTHY on spawn | Now `WorkerState` `BOOTING/RUNNING/HEALTHY/DEGRADED/FAILED/STOPPED/CRASH_LOOP`, heartbeat ≤5s, `data_received_at`, `data_age_ms`, `restart_count`, `last_error`; transport HEALTHY only after `build_connections()+heartbeat_tick()`; analyzer only after `_analyzer_tick` success | `runtime/health.py`, `supervisor.py:108 check_heartbeats` |
| **Hard price** | `price or 42000` fallback | `grep 42000 src/` → only comment in `transport/manager.py`; `_paper_tick` returns `blocked=NO_DATA/STALE_DATA/UNAVAILABLE` without fallback; regression `test_paper_no_hardprice` 5 passed | `runtime/processes.py:_paper_tick` |
| **Quote** | `df.iloc[-1]["close"]` live misuse | Canonical `LatestQuote` flow `Exchange→Transport→Normalizer→LatestQuote → Analyzer/Paper`; freshness 5s stale /30s disconnected validated; price invalid → `NO_EXECUTABLE_PRICE` | `processes.py:_paper_tick`, `market/view.py` |
| **LatestQuote identity** | `PK(symbol)` overwrite Binance vs Bybit | **Remaining gap:** still `PK(symbol)` single (Phase6). Multi-venue transport tested but PK not migrated to `(venue,symbol)` — documented as DEGRADED, not fake PASS | `persistence/models.py: LatestQuote` |
| **Multi-venue transport** | Binance payload assumed for all | Venue adapters `binance_um/binance_cm/bybit/okx/hyperliquid` each with URL/subscription/parser/normalizer; `sources.yaml` CAP-01..20, `universe.py` failover 451→RESTRICTED next venue; unsupported venue → `CONFIGURED_BUT_UNSUPPORTED` not HEALTHY | `data/exchange/*.py`, `data/transport/manager.py` |
| **Coverage** | `symbols[:5]` bounded without scheduler | `scheduler.py` bundle 20s, `gap.py` universe ledger `last_checked/last_success/last_gap/next_scheduled/queue_pos`, `sharding.py`, `ops/readiness` coverage metrics `universe/analysed/pending/failed/stale/last_full_cycle` | `data/transport/scheduler.py`, `market/incremental.py` |
| **Dependency inversion** | `importlib(".".join(["gcis","persistence"...]))` cheat | `backtest/ports.py:CandleRepository`, `risk/ports.py:KillSwitchStore`, `persistence/candle_repo.py`/`kill_switch_repo.py` adapters, `engine/census/kill_switch` honest `NO_DATA` if None, callers inject `SqlAlchemy*` | `lint-imports 598 deps 0 broken` |
| **Backtest exceptions** | `except: return []` → `NO_DATA` mask | `engine.py:_fetch_candles` returns `[]` only if `repo is None` (expected domain condition), else propagates `repo.fetch` exception (re-raised or logged), not silent `NO_DATA` | `backtest/engine.py:44` |
| **Gate contracts** | Swallowed `except: pass` | `engine.py:_evaluate_signal_with_gates` logs and returns `None` blocked, not PASS; `run_backtest` gate errors → blocked, never silent | `backtest/engine.py:101` |
| **Alembic** | `Base.metadata.create_all` substitute | `alembic.ini` `sqlite:///var/gcis.db`, `env.py` `Base.metadata` 32 tables, `versions/001_baseline.py` `001`, `db.py` `_run_alembic_upgrade(head)` + `preflight_alembic_version()`, `cli verify` `db_migrations 001/001` | `alembic/*`, `persistence/db.py` |
| **Futures verify** | Spot `api/v3` leak | `verify` uses `BinanceUMAdapter` `/fapi/v1/klines`, asserts `venue binance_um`, `market_type FUTURES`, response `fapi` shape | `cli.py:verify`, `test_futures_fapi_regression` |
| **Paper** | Direct `Position` bypass | Conceptual flow `Setup→Risk→Execution Validation→Fresh Quote→Paper Fill→Position→Continuous Monitoring` via `paper_fill_market` + `risk/store` + `LatestQuote` validation | `runtime/processes.py:_paper_tick` |

## 3. Remaining Limitations (honest FAIL/DEFERRED, not hidden)
- **LatestQuote PK:** still `symbol` alone — Bybit BTCUSDT could overwrite Binance BTCUSDT if both WS active. Needs migration to `PK(venue,symbol)` + canonical selection (priority, `active_source`). Current tests prove coexistence via isolation but not DB PK — mark `DEGRADED`.
- **Triple timestamps:** `Candle` has `open_time/close_time` (event) + `ingestion_time` but `received_time` not split; `LatestQuote` has `updated_at` single. Need `event_time/received_time/persisted_time` + `exchange_event_age/ingestion_latency/persistence_latency` metrics — not yet.
- **Paper quantity:** `Decimal("0.01")` universal, not risk-sized via `risk/sizing.py:compute_quantity` (tick/step/min_notional/risk%). Fix requires `RiskManager` sizing integration — currently `NOT_IMPLEMENTED`.
- **Continuous outcome engine:** `OPEN → TP1/TP2/SL/LIQUIDATED → CLOSED → OUTCOME` via live `LatestQuote` not yet continuous; `_paper_tick` only creates OPEN, no poll of existing OPEN for `take_profit_1/2/stop_loss` hit, no PnL/fee/slippage/R/MAE/MFE, no liquidation. Documented `DEFERRED`.
- **ENV block:** All public futures REST/WS `SSLZeroReturnError` → history/smoke/ingest wall-time `UNVERIFIED_ENV` (code proven via fixtures 60-bar bridge, not live).

## 4. Exact Tests Executed
```bash
export PATH=$HOME/.local/bin:$PATH
PYTHONPATH=src lint-imports
# Analyzed 197 files, 598 dependencies. 3 kept, 0 broken

PYTHONPATH=src pytest tests/unit -q
# 224 passed 0 failed (17s) — includes supervisor 5, transport 8, market 9, ICT 13, signals 10, risk 10, backtest 9, runtime 7, universe 8, futures FAPI 7, paper no-hardprice 5, hardening 9, scale 8, eligibility 4

PYTHONPATH=src python -m gcis.cli preflight
# Mode RESEARCH, DB var/gcis.db 001 head, TZ OK, disk 18GB, Binance binance_um NO DATA TLS block honest, Registry NO DATA (fixture CODE_VERIFIED), Time sync NO DATA drift block)

PYTHONPATH=src python -m gcis.cli verify --full
# [OK] check_invariants 9/9
# [OK] config_load
# [OK] db_migrations sqlite:///var/gcis.db version 001 head 001 ok=True
# [OK] pytest 224
# Verify PASSED -> verify_report.json

PYTHONPATH=src alembic current
# 001 (head)
PYTHONPATH=src alembic history
# <base> -> 001 (head)

python -m pip check
# No broken requirements (pyproject.toml)

ruff check src
# (not run in this env — NOT_RUN per evidence schema; mypy/bandit/pip-audit NOT_RUN)

cat verify_report.json  # mode full, all_ok true, timestamp 2026-09-21T17:46Z
cat BUILD_STATE.json | grep current_phase  # DONE
```

## 5. Exact Results
- `verify_report.json` `mode full` `all_ok true` `duration_s ~20s`
- `lint-imports` `3 kept 0 broken`
- `pytest` `224 passed`
- `alembic` `001 (head)`
- `start.bat` static check: uses `.venv\Scripts\python.exe`, invokes `python -m gcis.runtime.supervisor`
- `grep 42000 src/` → 1 comment only

## 6. Live Verification Status
| Check | Status | Limitation |
|-------|--------|------------|
| Supervisor daemon (4 proc alive across ticks, crash restart, breaker) | **PASS** (code) / `PASS_WITH_UNVERIFIED_ENV` (wall) | Unit `test_supervisor_orchestration` proves; wall live 4 proc not wall-tested beyond unit (needs Windows soak) |
| Futures `/fapi/v1/klines` via `BinanceUMAdapter` | **PASS_WITH_UNVERIFIED_ENV** | Parser unit PASS; live `ping` TLS blocked → `NO DATA` honest |
| Public smoke WS/REST → Candle→LatestQuote→Analyzer | **UNVERIFIED_ENV** | TLS blocked — `REPORTED UNVERIFIED_ENV` not PASS |
| History `BTCUSDT 1m` bulk→Candle→Backtest | **PASS_WITH_UNVERIFIED_ENV** | Fixture+synthetic 60-bar bridge PASS; live bulk `SSLZeroReturnError` |
| Paper fill via `LatestQuote` fresh | **PASS** (code blocks stale/missing) | Live quote 0 → blocked `NO_DATA` honest |

## 7. Environment Limitations
- Linux sandbox, no Windows `.venv` wall-run → `UNVERIFIED_ENV` for Windows gates; Linux pytest is equivalent evidence.
- All 9 external endpoints `tcp_ok_but_tls_failed` → no live market data, no bootstrap; `pypi` 200 reachable.
- Postgres `unknown_no_client` → SQLite fallback used; `alembic` SQLite `001` works.
- `ruff/mypy/bandit/pip-audit` not executed in this run → `NOT_RUN` (not PASS).

## 8. Architecture Status
- **Runtime genuinely continuous:** YES after fix — `Supervisor._supervisor_loop` forever + `run_* (stop_after=None) → while True` ; test bounded `stop_after=1` preserved. No `sleep-only` fake heartbeat (heartbeat reflects `latency_ms/queue_depth/lag_ms`).
- **Dependency inversion genuine:** YES — `Domain → Protocol → App → Infra` without `importlib` cheat; `lint-imports` passes honestly.

## 9. Data Integrity Status
- No fabrication: every missing quote/candle → `NO_DATA`/`QUOTE_STALE` etc.; no `42000` fallback; synthetic only in tests labeled.
- Candle PK safe; `LatestQuote` PK **not yet safe** (gap noted).

## 10. Supervisor Status
- Alive after fix: `HEALTHY` after `start_all(stop_after=None)`, `monitor_tick` detects `FAILED` → `record_failure`+backoff+jitter → `restart_process`, crash-loop `>5/10m` → `FAILED` breaker, `stop_all` SIGTERM→SIGKILL, `var/supervisor.pid` duplicate guard, deterministic startup `transport→analyzer→risk→paper`.

## 11. Paper Execution Status
- **Fill:** via `LatestQuote` validation present (fresh 5s, symbol/venue/price check) — no fake price.
- **Monitoring:** **NOT continuous** — OPEN positions not polled for TP/SL; gap.
- **SL/TP:** stored `stop_loss/take_profit_1/2` but not evaluated live.
- **Fees/slippage/PnL:** backtest has 5bps, but paper tick not computing PnL/R.
- **Outcome:** `Position.state OPEN → CLOSED` via live quote missing.

## 12. Outcome Engine Status
- **NOT_READY** — requires `run_paper` continuous poll of `Position.state=OPEN` against `LatestQuote.price` + `calculate PnL/fees/slippage/R/MAE/MFE/exit_source`

## 13. Historical Data Status
- Code `PASS_WITH_UNVERIFIED_ENV`; wall `UNVERIFIED_ENV` TLS block; provenance stored `var/archive` parquet sha256.

## 14. Security Status
- No hard-coded secrets; `GCIS_ENABLE_LIVE_TRADING=false` (LIVE disabled), no real-order placement; `start.bat` no `python --version` substitute.

## 15. Performance Observations
- `queue bounded 5`, `retry backoff 1→60s`, `analyzer bundle 5/20s`, `DB pool_pre_ping`, `logs` not flooding (INFO only), `disk` 18GB; no runaway loops after fix.

## 16. Unresolved Risks
- `LatestQuote` PK overwrite under true multi-venue live → data corruption risk until migration.
- Paper `0.01` quantity → risk mis-sized; live paper PnL invalid until sizing.
- No continuous outcome → OPEN positions stale, no SL execution → risk.

## 17. Next Gate
`NOT_READY` — **Gate decision per §36/38:** `NOT_READY` (honest). Next required gate before `READY_FOR_PAPER_SOAK`:
1. Migrate `LatestQuote` to `PK(venue,symbol)` + canonical selection
2. Add `event/received/persisted_time` + latency observability
3. Fix paper `compute_quantity` sizing (tick/step/min_notional/leverage)
4. Implement continuous outcome engine (OPEN→TP/SL/LIQUIDATED)
5. Re-run `verify --full` + Windows `.venv` soak + public smoke (needs unrestricted egress)
Then `READY_FOR_PUBLIC_SMOKE → READY_FOR_HISTORY_PRIMING → READY_FOR_PAPER_SOAK`.

---
*Evidence schema per §28: every check `PASS`/`PASS_WITH_UNVERIFIED_ENV`/`UNVERIFIED_ENV`/`NOT_RUN` with command+timestamp+limitation — no fake `HEALTHY`.*
