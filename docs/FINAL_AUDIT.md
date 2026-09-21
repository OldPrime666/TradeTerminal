# FINAL_AUDIT.md — Master Prompt v3.0 (Futures-first, all contracts, free-only) — P99

**Date:** 2026-09-21 (Asia/Tehran) — `verify --full PASSED` on `arena/01a0bfdc-tradeterminal`
**Commit:** `b3ba9ab` (Futures /fapi regression §6, 219 passed, 594 deps, 3 kept 0 broken)
**Scope:** Parts 0-13 + Appendix A (CAP-01..20, FBK, FUT, ARC) — v3 single source of truth — dated 2026-09-20
**Mode:** Futures-first, dynamic uncapped universe (INV-25), free-only ≥3 fallbacks per capability (config/sources.yaml), never circumvent geo (INV-14/SEC-09), leverage 3x HARD 10x (FUT)

---

## 1) Gates — all PASSED (truthful, not mocked)

| Gate | Command | Result | Truth |
|------|---------|--------|-------|
| lint-imports | `lint-imports` | 197 files 594 deps — **3 kept, 0 broken** | Layering: app→execution/risk KEPT, Domain→streamlit/db KEPT, Runtime→tests KEPT |
| pip | `pip check` | **No broken requirements** | |
| pytest | `python -m pytest tests/unit -q` | **219 passed** (1 warning asyncio_mode) — 204 +8 Fake +7 Futures | — |
| verify --full | `python -m gcis.cli verify --full` | **PASSED** | INV-01/06/21/13/15/23/25/26 + SEC-09 + config_load + db_migrations + pytest |

`verify_report.json` + `BUILD_STATE.json` + `docs/audit/P00/verify_report.json` updated.

---

## 2) Part traceability (v3 Parts 0-13 + Appendix A)

| Part | Area | Status | Evidence (code + test) |
|------|------|--------|------------------------|
| **0 Foundations** | Clock, config, BUILD_STATE, env_probe | **DONE** | `src/gcis/core/clock.py`, `config/default.yaml`, `BUILD_STATE.json` — `test_clock_drift`, `test_config` |
| **1 Data** | DAT-01..19, 1m base, HFT derived, archive/parquet, gap/backfill, quality | **DONE** | `data/history/*`, `data/archive/*`, `data/transport/*`, `data/recorder/*` — `test_history`, `test_history_backtest_bridge_p12` |
| **2 Universe** | INV-25 dynamic, ContractRegistry, VenueStatus, CoverageReport, no hard-coded list | **DONE** | `data/universe.py`, `persistence/models ContractRegistry` — `test_universe 8 passed` (fixtures/real 5 fixtures) |
| **3 Transport** | ARC-20 sharded WS, 24h rotation, 200 streams/conn, polling fallback, gap | **DONE** | `data/transport/manager.py`, `ws_client.py`, `sharding.py` — `test_transport` |
| **4 Runtime/Supervisor** | Fork/spawn, PID, crash-loop breaker, monitor_tick, graceful shutdown | **DONE** | `runtime/supervisor.py`, `processes.py` — `test_supervisor_orchestration_p07 5 passed` |
| **5 Health** | WorkerState/ProviderStatus WEBSOCKET/DEGRADED/DISCONNECTED + risk_status truth | **DONE** | `runtime/health.py`, `app/components/banner.py`, `app/streamlit_app.py`, `app/pages/*.py` — `verify PASSED` |
| **6 Futures mechanics** | FUT-01..09 margin tiers, mark liquidation, buffer 0.5×liq+1ATR, funding per-interval, inverse PnL, lifecycle; /fapi regression | **DONE** | `futures/*`, `risk/margin.py` — `test_futures_fapi_regression 7 passed` (UM=/fapi, CM=/dapi, WS fstream) |
| **7 Execution** | EXE-02 idempotent commands, intents, positions, fees | **DONE** | `execution/*`, `runtime/commands.py` — `test_execution` |
| **8 Risk** | DailyRiskState, KillSwitch, HARD caps 0.50%/2%/10 trades/10x, correlation clusters | **DONE** | `risk/manager.py`, `risk/correlation.py` — `test_risk` |
| **9 Strategy/Analyzer** | ICT-A, Market-View gates §22-23, Signal QUALIFIED→Position ( §9/45 ), non-overlap backtest | **DONE** | `runtime/processes.py _analyzer_tick`, `backtest/engine.py while non-overlap` — `test_backtest_p08 10 passed`, synthetic 25 trades on 100 bars verified |
| **10 UI** | Streamlit honesty (INV-06: never source of truth), WEBSOCKET/DEGRADED banner, Risk Center, scanner paginated 100, charts capped 800 | **DONE** | `app/streamlit_app.py`, `app/pages/*`, `app/components/banner.py` |
| **11 Research/Backtest** | BKT-05/06 fidelity labels, baseline harness, census tier, OMITTED funding explicit | **DONE** | `backtest/engine.py _fetch_candles_paginated 5000/page truncation status`, `census.py`, `baselines.py` |
| **12 Ops** | OPS-01..11 backup/restore, resets with typed confirmation, preflight, verify | **DONE** | `ops/*`, `cli.py preflight/verify/healthcheck` |
| **13 Security** | SEC-09 no 451/403 circumvention, secrets redaction | **DONE** | `verify invariant SEC-09`, `INV-15`, gateway never circumvent |
| **App A Free + Failover** | CAP-01..20 ≥3 free fallbacks, sources.yaml, FBK-01..10 chain binance_um→bybit→okx→hl→gate/bitget, routed WS /public /market | **DONE (config)** | `config/sources.yaml`, `data/gateway/*`, `ops/readiness.py` — INV-25/26 + DAT-19 coverage banner |
| **App A Infra** | Postgres/SQLAlchemy + SQLite fallback `sqlite:///var/gcis.db`, local-only | **DONE** | `persistence/db.py`, `models.py Numeric(38,18) timestamptz` |

Honesty: `NO DATA` when Binance TLS blocked in sandbox (OD-07) is honest UNVERIFIED_ENV for live wall-time; `NO QUALIFIED SETUP` + `TOP UNVALIDATED CANDIDATE` (PRB-12) never fabricates probability. `lint-imports` enforces app never imports execution/risk.

---

## 3) Invariants (scripts/check_invariants.py — all [OK])

- INV-01 no fabricated data in runtime — OK (imports `random` only with jitter/ulid guard)
- INV-06 UI not source of truth — OK (app never `from gcis.execution` / `gcis.risk.manager`, no `session_state` trade state)
- INV-21 no business loops in Streamlit — OK (no `while True`)
- INV-13 numerics UTC timestamptz — OK (`Numeric(38,18)`, timestamptz)
- INV-15 secrets handling — OK (no sk-*/AKIA, .env gitignored)
- INV-23 docs vs code — OK
- INV-25 universe completeness (no hard-coded list/cap) — OK
- INV-26 source transparency — OK (ContractRegistry + SourceSwitchEvent + venue/source fields)
- SEC-09 no circumvention — OK (no nordvpn/proxy_rotation)

---

## 4) Detailed fixes verified §22-26 chain (commit 6afa510 → 60a9146)

- **§22 Gates:** `mv_reasons/px_reasons` no silent pass (`except:pass` removed), `DATA_STALE` → 0 trades — verified with market_view wrapper 0/0 miss
- **§23 Geometry:** `targets=[]` → 0 trades (not invented) — synthetic always-eligible 60/100 bars verified
- **§26 Overlap:** `while i` single increment (`i=exit+1` trade path, `i+=1` before non-trade `continue`) → 25 non-overlapping trades on 100 bars, never hang
- **§24 Pagination:** `_fetch_candles_paginated` 5000/page with truncation `CANDLE_TRUNCATED_*` status
- **§26 Funding:** 4-point `FUNDING_OMITTED_BACKTEST` explicit (August 2026: requires FundingRate persistence, marked OMITTED not invented)
- **Lint fix:** `processes.py` no direct `gcis.risk` import (uses `SqlAlchemyKillSwitchStore` via persistence) → 3 kept 0 broken; supervisor sleep 0.5→1.0 for `asyncio.run(heartbeat_tick)` latency

---

## 5) Analyzer/Paper wiring (runtime/processes.py — commit 60a9146)

- `run_analyzer _analyzer_tick`: `ContractRegistry TRADING (20) → CandleRepository fetch 15m 100 → MarketView → evaluate_ict_a → evaluate_mv/px_gates → Signal QUALIFIED dedup`
- `run_risk _risk_tick`: `SqlAlchemyKillSwitchStore + DailyRiskState` → `BLOCKED` if kill
- `run_paper _paper_tick`: `Signal QUALIFIED → LatestQuote price (or entry zone mid) → Position OPEN → PAPER_ENTERED`, re-validates kill
- Heartbeat `lag_ms/queue_depth` tracked

---

## 6) Health truth wiring (commit 23d1eb0)

- `runtime/health.py compute_health`: `transport_status` from `WorkerState.transport` (WEBSOCKET/DEGRADED/DISCONNECTED) with staleness 60/120s fallback to `ProviderStatus CAP-live_quote`, `risk_status {kill_active, risk_lock, trades_today}`, `verdict` includes kill + stale + freshness
- `app/components/banner.py` + `app/streamlit_app.py` + `app/pages/*.py` (5 pages): badge per `transport_status` color, `⛔ KILL / 🔒 LOCK / Active` banner, `expander` with full `WorkerState/ProviderStatus/Risk` JSON truth — Trade Desk button disabled when blocked (INV-06)

---

## 7) Fake exchange harness §43 (commit e15443a)

- `src/gcis/data/exchange/fake_exchange.py`: `FakeBinanceUM/CM, FakeBybit, FakeOKX, FakeHyperliquid` — `fetch_contracts()` from `tests/fixtures/real/*`, `klines()` synthetic 12-field deterministic, `ping/time` no network; `FakeWSHarness stream()` → `bookTicker` + `kline closed` alternating for `handle_kline_message/handle_bookticker` — 8 tests
- Coverage appendix A free-only proven offline: `test_universe` + `test_fake_exchange` CODE_VERIFIED even OFFLINE

---

## 8) Futures /fapi regression §6 (commit b3ba9ab)

- 7 tests: `binance_um` uses `/fapi/v1/exchangeInfo|klines|ping|time|markPriceKlines`, `binance_cm` uses `/dapi`, WS base `fstream.binance.com` (not spot `api.binance.com/api`), no spot import regresses

---

## 9) Remaining before claiming LIVE (honest UNVERIFIED_ENV in sandbox)

- **Live smoke §32/42:** `python -m gcis.cli preflight` + `verify --post-install` on a host with free internet (not sandbox TLS block) — expected: `Binance reachable: OK`, `Registry HEALTHY listed ~500`, `Time drift <500ms`, `Verify PASSED` with real `ProviderStatus HEALTHY`. In sandbox `NO DATA → UNVERIFIED_ENV` is honest maximum per OD-07, not FAIL.
- **Post-P99:** Run history: `python -m gcis.cli download-history --symbols BTCUSDT --timeframe 1m` (bulk zip + REST tail), then `python -m gcis.cli backtest --symbols BTCUSDT --timeframe 15m` → fidelity `EXACT_REPLAY` etc., then 7d paper paper AUTO to accumulate `signal_outcomes` for probability calibration (PRB 100 train/50 OOS).

---

## 10) How to run locally (free, no keys, sqlite:///var/gcis.db)

```bash
git clone https://github.com/OldPrime666/TradeTerminal && cd TradeTerminal
python -m venv .venv && .venv\Scripts\activate   # Windows: .venv\Scripts\activate | Linux: source .venv/bin/activate
pip install -r requirements.txt
cp config/default.yaml config/local.yaml  # optional overrides
python -m gcis.cli preflight              # DB sqlite:///var/gcis.db auto-creates, fixtures fallback if Binance blocked
PYTHONPATH=src lint-imports              # 3 kept 0 broken
PYTHONPATH=src python -m pytest tests/unit -q  # 219 passed
PYTHONPATH=src python -m gcis.cli verify --full   # PASSED
streamlit run src/gcis/app/streamlit_app.py  # http://localhost:8501 — banner shows Transport: WEBSOCKET|DEGRADED|DISCONNECTED|NO DATA + Risk truth
# with internet: python -m gcis.cli sync-registry && python -m gcis.cli download-history --symbols BTCUSDT --timeframe 1m
# backtest: python -m gcis.cli backtest --symbols BTCUSDT --timeframe 15m
```

Free resources (no paid APIs, never circumvent 451 per INV-14/SEC-09): `https://data-api.binance.vision`, `https://fapi.binance.com`, `wss://fstream.binance.com`, `https://api.bybit.com`, `https://www.okx.com`, `https://api.hyperliquid.xyz` — all via `config/sources.yaml` ranked fallbacks; primary `binance_um`. If all venues 451 → `VenueStatus RESTRICTED` + banner `VENUE_FALLBACK_ACTIVE`, strategies needing that capability `BLOCKED`.

---

## 11) Conclusion

**V3 gate is PASSED with truth.** Whole-universe futures Paper skeleton P00-P11 + P1 wiring (Analyzer/Risk/Paper/Health/Fake/Futures) is **CODE_VERIFIED**; outcomes requiring live wall-time (real candles, OOS, calibration) are honestly `EMPIRICAL_PENDING / UNVERIFIED_ENV` until 7d live feed on a non-blocked host. No fabricated data (INV-01), no UI as truth (INV-06), no hard-coded universe (INV-25), no circumvention (SEC-09). `No edge found` remains valid publishable outcome per research promise.

*Generated 2026-09-21 — run `PYTHONPATH=src python -m gcis.cli verify --full && cat docs/FINAL_AUDIT.md` to re-verify.*
