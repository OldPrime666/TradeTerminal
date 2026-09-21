# REMEDIATION BASELINE — TTAgent / TradeTerminal

**Date:** 2026-09-21 18:10 UTC  
**Commit inspected:** `dbda435` (Phase7+8 honest) + Phase1 continuous fix 2026-09-21 18:10  
**Environment:** Linux 6.1, Python 3.11.2, SQLite var/gcis.db (Alembic 001), network `tcp_ok_but_tls_failed:SSLZeroReturnError` on all Binance/Bybit/OKX/Hyperliquid/data.binance.vision (UNVERIFIED_ENV)

## 1. Entry Points & Process Model
- `start.bat` → preflight → `python -m gcis.runtime.supervisor` (start "GCIS Supervisor" /min) → `streamlit run src/gcis/app/streamlit_app.py` on 127.0.0.1:8501 — uses `.venv\Scripts\python.exe` preferentially, fails fast if preflight exit 1.
- `src/gcis/runtime/supervisor.py`: `Supervisor` class, 4 roles `transport/analyzer/risk/paper`, `multiprocessing.get_context("spawn"/"fork")`, pid tracking, `WorkerState` heartbeat ≤5s, `BACKOFF_SCHEDULE [1,2,4,8,16,30,60]` + `uniform(-0.2,0.2)` jitter, crash-loop `>5/10m → FAILED`, `pidfile var/supervisor.pid` duplicate guard, `terminate()→join(5)→kill()` graceful, `monitor_tick()` + `_supervisor_loop(interval=2)` continuous. **Gap fixed 18:10:** `start_process` now defaults `stop_after=None` (continuous) else test `stop_after=1`; `_supervisor_loop` calls `start_all(stop_after=None)`.
- `src/gcis/runtime/processes.py`: `run_transport/analyzer/risk/paper(stop_after=1)` — transport uses `TransportManager`, analyzer uses `MarketView+ICT+ gates`, risk uses `SqlAlchemyKillSwitchStore`, paper uses `LatestQuote` canonical. **Gap fixed:** analyzer/risk/paper now handle `stop_after=None` as `while True: tick; heartbeat; sleep(0.3)` until SIGTERM; transport already had `run_forever_sync()` for None.
- `src/gcis/runtime/health.py:compute_health()` → `verdict` HEALTHY/DEGRADED/DISCONNECTED/NO DATA from `WorkerState` + `ProviderStatus`.

## 2. Persistence & Migrations
- `src/gcis/persistence/db.py`: `Base(DeclarativeBase)`, `get_engine()` ensures var dir, `init_db()` now runs `_run_alembic_upgrade(head)` via `alembic.command.upgrade` (no `create_all` fallback), `preflight_alembic_version()` checks `alembic_version` vs `ScriptDirectory.head`.
- `alembic/`: `alembic.ini` `sqlalchemy.url=sqlite:///var/gcis.db`, `alembic/env.py` imports `Base.metadata` (32 tables), `_get_db_url()` from `get_config()`, `alembic/versions/001_baseline.py` revision `001` creates 32 tables (candles, latest_quotes, contract_registry 2 indices, etc.). `alembic current` → `001 (head)`, `history` → `<base> -> 001`. `verify` `db_migrations` checks `001/001 ok=True`.
- `isolation test fixtures` use `Base.metadata.create_all` on `sqlite:///:memory:` or `tmp_path` — allowed.

## 3. Transport & Data
- `config/sources.yaml` + `DATA_SOURCE_MATRIX.md`: vetted free sources CAP-01..20, venue_chain `binance_um→bybit_linear→okx_swap→hyperliquid` (BinanceUM default).
- `src/gcis/data/universe.py`: `_load_adapter` via `importlib` for `ADAPTERS` dict (BinanceUM, BinanceCM, Bybit, OKX, Hyperliquid), `sync_registry()` failover on 451/403/timeout → `RESTRICTED/DISCONNECTED` → next venue, `SourceSwitchEvent`, fixture fallback only if `use_fixtures_on_failure=True`.
- `src/gcis/data/transport/manager.py`: venue-specific adapter/parser/normalizer, WS kline → canonical `Candle` (unique `uq_candle_venue_symbol_tf_open`), idempotent `gap.py`, `scheduler.py` bundle budget 20s, `polling.py` fallback, `sharding.py`. Health truthful: `ws_state` only HEALTHY after `build_connections()` + `heartbeat_tick()` success.
- `src/gcis/data/history/loader.py`: bulk `data.binance.vision` zip → `pyarrow` parquet `var/archive/<venue>/<symbol>/<tf>/YYYY-MM-DD.parquet` + REST tail, `ingest_rows_to_parquet` sha256 + dedup + `check_disk_budget`.

## 4. Quote & Candle Models
- `src/gcis/persistence/models.py`: `LatestQuote` PK now `(venue,symbol)`? **Inspect:** currently `PrimaryKeyConstraint('symbol')` alone + `venue` column non-PK — multi-venue overwrite risk. **Baseline gap:** multi-venue identity not safe per Phase6 (needs `(venue,symbol)` PK). Status: `CODE_VERIFIED` per BUILD_STATE but architecturally DEGRADED — requires migration.
- `Candle` PK `id` + unique `(venue,symbol,timeframe,open_time)`, correct for multi-venue.
- Quote flow: `Exchange→Transport→Normalizer→Canonical LatestQuote → Analyzer/Paper/Risk/UI`. Freshness `freshness.quote_stale_after_s=5`, `quote_disconnected_after_s=30` validated in `_paper_tick` and `Analyzer` via `MarketView`.
- Timestamps: `LatestQuote.updated_at` (event/received?), `Candle.open_time/close_time` (event), `ingestion_time`/`persisted_time` present? Check: `Candle.ingestion_time`, `LatestQuote.updated_at` as event; `received_time` not explicit — **gap**: needs triple timestamp per Phase7.

## 5. Strategy Pipeline
- `src/gcis/market/view.py:MarketView(as_of)` causal (no lookahead), `src/gcis/ict/*` 13 modules (structure, displacement, FVG, order_blocks, sweeps, mitigation, breaker, premium, htf), `src/gcis/strategies/ict_a.py:__version__ 0.1.0`, `src/gcis/signals/gates.py: evaluate_mv_gates/evaluate_px_gates` 30+ gates, `src/gcis/signals/fusion.py` score grades, `src/gcis/signals/lifecycle.py` state machine, `src/gcis/signals/outcome_tracker.py`.
- Gates never swallow: `evaluate_ict_a` + gates wrapped in try/except → block on error (not PASS).

## 6. Paper Execution
- `src/gcis/execution/paper.py: paper_fill_market/tick` uses `ask+slippage`/`bid-slippage` 5bps taker, never mid; limit requires `trade_through 1 tick`; `evaluate_exits` pessimistic `AMBIGUOUS_STOP_FIRST`.
- `src/gcis/runtime/processes.py:_paper_tick`: `Signal QUALIFIED → LatestQuote` validation (freshness 5/30s, price>0, source/venue, symbol match) → `Position` (quantity `0.01` hard-coded — **gap** per Phase16 should use risk sizing `compute_quantity`), `sig.state → PAPER_ENTERED`. No fallback `42000` (checked `grep 42000 src/` → only comment).
- Outcome: `src/gcis/execution/positions.py: update_position_mark/close_position`, but continuous monitoring via `_paper_tick` only on new signals, not existing OPEN positions SL/TP/liquidation via live quote — **gap** per Phase17 (needs continuous outcome engine).
- Fees/slippage: taker 5bps entry+exit applied in backtest; paper currently shows `quantity 0.01` + price validated but not risk-sized — **gap**.

## 7. Verification & Evidence
- `src/gcis/cli.py`: `preflight` (config, DB, tz, disk, Binance ping, registry sync, time drift), `verify` (check_invariants 9/9, lint-imports 3/3 598 deps, config_load, db_migrations 001/001 via `preflight_alembic_version`, pytest), `download-history`, `backtest`, `healthcheck`, `sync-registry`, `census`.
- `scripts/check_invariants.py`: 9 checks, `lint-imports` contracts `app cannot import execution/risk`, `Domain must not import streamlit/httpx/websockets/sqlalchemy` — now honest (ports).
- `BUILD_STATE.json`: `current_phase DONE`, 24 phases CODE_VERIFIED, `migration_head sqlite_init` (stale vs 001), `last_verify verify --quick 0` at 2026-09-21T17:29+00.
- `verify_report.json`: last quick PASSED 2026-09-21T17:29; `docs/audit/P00` copy.

## 8. Testing
- `tests/unit` 224 tests `PYTHONPATH=src pytest -q` 224 passed 17s (was 219). Coverage: supervisor, health, transport, market, ICT 13 goldens+no_repaint, signals 10, risk 10, backtest 9, runtime 7, universe 8, DOM CCXT parity, futures FAPI regression 7, paper no hardprice 5.
- `lint-imports` 3 kept 0 broken, `ruff`/`mypy`/`bandit`/`pip-audit` available via `pyproject.toml dev`.

## 9. Gaps Summary (honest baseline — not PASS)
- **P1 fixed 18:10** — now continuous; previously one-shot default.
- **P6 LatestQuote PK** — single-venue overwrite risk, needs `(venue,symbol)` migration.
- **P7 triple timestamps** — missing explicit `received_time/persisted_time` + latency metrics.
- **P16 quantity** — paper `0.01` universal, not risk-sized.
- **P17 outcome engine** — no continuous SL/TP/liquidation monitor for OPEN positions (paper tick only creates, not closes via quote).
- **Network ENV** — all venues TLS blocked → history/smoke wall-time UNVERIFIED_ENV (code proven via fixtures).
- **BUILD_STATE migration_head stale** — shows `sqlite_init` not `001`.

No fabricated data, no hard-coded 42000 runtime price, no circumvented Import Linter after fix, no `create_all` substitute after fix.

---
*Teams: Senior eng / Architect / Quant infra / Data-eng / QA — factual only, no fake PASS*
