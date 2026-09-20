# IMPLEMENTATION_PLAN.md — Phase checklist (v3.0 Futures-first P00-P11 = M0)

## P00 Foundations — CODE_VERIFIED 2026-09-20
- [x] Inspect repo → docs/REPO_AUDIT.md
- [x] Run scripts/env_probe.py → BUILD_STATE.json
- [x] Create AGENTS.md / CLAUDE.md (Part0+1)
- [x] Create config/default.yaml (Part12) + docs/*
- [x] Create pyproject.toml + requirements.in + .env.example
- [x] Create src/gcis core: enums, clock, ids, config, versioning
- [x] Create persistence models + db (SQLite fallback)
- [x] Create market: candles, indicators, sessions, regime, view
- [x] Create ICT detectors: swings, structure, displacement, FVG, OB, sweeps
- [x] Create strategy ICT-A, signals gates/fusion/lifecycle, risk manager, paper fills
- [x] Create data: binance adapter, gateway
- [x] Create runtime health + app streamlit_app
- [x] Create cli + verify harness + invariant scanner
- [x] Install deps, run preflight, run verify --quick, fix failures
- [x] Write docs/audit/P00/REPORT.md
- [x] Tag phase-P00, advance BUILD_STATE to P01

## P01 Universe & gateway — CODE_VERIFIED 2026-09-20
- [x] Binance UM/CM adapters: GET /fapi/v1/exchangeInfo + /dapi/v1/exchangeInfo, parse filters → normalized contracts (LINEAR/INVERSE, tick/step, marginAsset, contractType map) — `src/gcis/data/exchange/binance_um.py`, `binance_cm.py`
- [x] Bybit adapter: GET /v5/market/instruments-info?category=linear|inverse → normalized — `bybit.py`
- [x] OKX adapter: GET /api/v5/public/instruments?instType=SWAP|FUTURES → normalized — `okx.py`
- [x] Hyperliquid adapter: POST /info {"type":"meta"} → normalized — `hyperliquid.py` + `base.py` interface (free-only, geo-detect 451/403, no circumvention)
- [x] Universe service: `src/gcis/data/universe.py::sync_registry` — loops venue_chain `binance_um→bybit→okx→hyperliquid` with failover, 50% budget via ProviderGateway, updates VenueStatus/ProviderStatus (HEALTHY/RESTRICTED/DISCONNECTED, latency_ms, circuit_state), SourceSwitchEvent, ContractStatusHistory, CoverageReport (listed/analysable/warming_up/excluded/not_subscribed/stale), asset_class tagging, idempotent upsert — no hard-coded list (INV-25)
- [x] Time sync: `src/gcis/data/time_sync.py` — venue time → NTP pool → HTTP Date → NO DATA, drift warn 500/block 2000
- [x] Recorded fixtures: `tests/fixtures/real/binance_um_exchangeInfo.json` (5 symbols), bybit/okx/hyperliquid JSON + 8 unit tests `tests/unit/test_universe.py` (parse 4 venues, sync via fixture OFFLINE, idempotency, NO DATA honest, no-hardcoded scan)
- [x] CLI: `python -m gcis.cli sync-registry [--use-fixtures]` + enhanced `preflight` (registry sync + time sync) + verify harness
- [x] Env probe: `scripts/env_probe.py` v3 9 venues, BUILD_STATE network_venues
- [x] Invariants: `scripts/check_invariants.py` 9/9 OK (INV-25/26 + SEC-09), `scripts/source_matrix_check.py` 18/18 PASSED
- [x] DB: `var/gcis.db` migrated (drop/recreate for new columns), seeded 5 contracts (BTCUSDT etc.), var/gcis.db → `contract_registry:5, coverage_reports:1, venue_status:4`
- [x] Docs: REQUIREMENTS_TRACEABILITY.md DAT-01..03,15, trace updated; docs/audit/P01/REPORT.md written
- [x] Verify: `verify --quick` + `verify --full` PASSED 24 tests (8 new), check_invariants 9/9, source_matrix 18/18
- Next: tag `phase-P01` commit, advance BUILD_STATE to P02

## P02 Historical — CODE_VERIFIED 2026-09-20
- [x] Archive store: `src/gcis/data/archive/store.py` — Parquet+zstd `var/archive/<venue>/<symbol>/<tf>/YYYY-MM-DD.parquet`, `write_parquet`/`read_parquet`/`df_from_bulk_rows`/`derive_timeframe` (ARC-20a 1m base only, HTF derived via resample 1m→5m/15m/1h/4h/1d, checked), `normalize_timestamp_to_us` (ms/µs→µs), `check_disk_budget` (10GB warn /2GB BLOCK), idempotent dedup open_time
- [x] Bulk: `src/gcis/data/history/bulk.py` — `BINANCE_VISION_BASE data/futures/{um,cm}/daily|monthly/klines/...` daily/monthly zip chain, `.CHECKSUM` verify, `zipfile`+`csv`, `parse_binance_kline_csv_row` (open_time us, Decimal strings), `download_range` dedup+sort, geo 451/403 → [] no circumvention, fallback bybit stub — free only
- [x] Quality: `src/gcis/data/quality/report.py` — `TIMEFRAME_US`, `detect_gaps` (interval*1.1), `quality_report` (total/expected/missing/gap_count/gaps_sample/first/last/status OK/GAP/INSUFFICIENT_HISTORY <300), `check_aggregation_mismatch`
- [x] Loader: `src/gcis/data/history/loader.py` — `ingest_rows_to_parquet` (dedup, df_from_bulk_rows, check identical skip, disk budget, write + archive_segments upsert version p02-1m-base), `load_from_bulk` (90d default, partition by date, write per day, quality_report, fast offline TLS-block → NO DATA honest), `load_from_rest_tail` (BinanceUMAdapter.klines → normalize → partition), `download_history` (resolve symbols from ContractRegistry if None, disk BLOCK, bulk+tail per symbol with combined status, log), market um/cm
- [x] Binance UM klines: added `klines` + `mark_price_klines` to `binance_um.py` (ms/µs handling)
- [x] Fixtures & tests: `tests/unit/test_history.py` 8 tests — parse row, normalize ts, archive idempotent (write/read/dedup), bulk mock 2-day zip →3 rows sorted, quality gap vs no-gap, derive 5m from 5x1m → open 100 close 109 high 114, loader bulk+tail idempotent (tmp archive), loader registry symbols resolution via in-memory DB
- [x] CLI: `python -m gcis.cli download-history [--symbols ...] [--timeframe 1m] [--venue binance_um] [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--market um]` — prints bulk/tail per symbol + disk + gap, honest NO DATA when TLS blocked (fast path for 90d default → NO DATA offline sandbox honest), offline CODE_VERIFIED via tests
- [x] Demo archive: `var/archive/binance_um/BTCUSDT/1m/2024-01-01.parquet` (5 bars) + `2024-01-02.parquet` (3 bars) demo 8 bars, `archive_segments` 2 rows, `quality_report` gap 1 (1435 missing between days) → INSUFFICIENT_HISTORY demo; `derive_timeframe` 5m validated
- [x] Verify: `verify --quick` + `verify --full` PASSED 32 tests (8 new history), `check_invariants` 9/9 OK, `source_matrix_check` 18/18 PASSED (CAP-04 bulk still ≥3 fallbacks)
- Next: tag `phase-P02` commit, advance BUILD_STATE to P03

## P03 Live ingest — CODE_VERIFIED 2026-09-20
- [x] Sharding: `src/gcis/data/transport/sharding.py` — `shard_streams(180)`, `build_klines_streams(s@kline_1m)`, `build_all_market_streams(bookTicker+markPrice+!forceOrder@arr)`, `build_focus_streams(depth@0ms+aggTrade)`, `plan_shards(symbols,focus)` → klines shards ceil(N/180) per ARC-20, summary
- [x] WS client: `src/gcis/data/transport/ws_client.py::WSConnection` — combined stream URL `stream?streams=`, `should_rotate` 23h+15s overlap, `connect_and_serve` with `websockets` ping 180/600, state DISCONNECTED→CONNECTING→WEBSOCKET→RECOVERING, `backoff_schedule [1,2,4,8,16,30,60]`, `_serve_loop` JSON parse (combined stream `data` wrap), `on_message(ts_us)`, proactive `rotate<24h` close 1000
- [x] Polling fallback: `src/gcis/data/transport/polling.py` — `poll_klines(venue,symbols,interval)` REST `klines` limit2, `normalize_timestamp_to_us`, 451/403 → [] no circumvention, `polling_loop_should_run(ws_state,5s)` only when not WEBSOCKET
- [x] Gap: `src/gcis/data/transport/gap.py` — `detect_missing_intervals(sorted open_times, start,end, interval_us)` → missing intervals, `backfill_missing(gaps, max 1500)` via REST startTime, `should_trigger_backfill`
- [x] Raw recorder: `src/gcis/data/recorder/store.py` — `RAW_ROOT var/raw`, `raw_path(venue/day/stream-hour.ndjson)` hourly shards, `append_raw(venue,stream,payload,ts_us)` NDJSON envelope `_received_at/venue/stream/payload`, `list_raw/purge_expired(14d)`, `compress_raw` zstd hook (optional)
- [x] Manager: `src/gcis/data/transport/manager.py` — `WS_BASES` futures, `handle_kline_message` (WS kline `e/k/x` only closed `x=True` persisted, polling row `open_time` dict), `_persist_candle` (Decimal 38,18, high>=low check, unique (venue,symbol,tf,open_time) idempotent, `Candle` + `EventOutbox candle.closed entity_id venue:symbol:tf:open_time` + `ingest_rows_to_parquet` archive + `ProviderStatus CAP-03 data_age_s`), `TransportManager(venue,symbols,focus, max_per_conn 180, rotate 23h)` builds `plan_shards` → `WSConnection` per shard with raw recorder+handle, `health()` aggregates ws_state WEBSOCKET/DEGRADED/DISCONNECTED, `polling_tick` + `gap_tick` (detect missing via DB Candle query, backfill first gap) + `heartbeat_tick` (WorkerState transport), `run_forever` asyncio gather
- [x] Tests: `tests/unit/test_transport.py` 8 tests — shard 400→3 shards, WS rotate & URL, gap 1 missing (00:02), polling should_run states, raw recorder tmp NDJSON, candle persist idempotent (WS kline true→1 candle+1 outbox, duplicate→still 1), manager plan 5 symbols →3 conns (klines/all_market/focus)
- [x] Verify: `verify --full` PASSED 40 tests (8 new transport), `check_invariants` 9/9 OK (no while True in streamlit), `source_matrix` 18/18 (CAP-02 live 1m, CAP-03 REST, CAP-04 bulk still ≥3)
- Next: tag `phase-P03` commit, advance BUILD_STATE to P04

## ... (P04-P99 per PHASES.md v3: P04 Market, P05 ICT, P06 Strategy, P07 Risk&Paper, P08 Backtest, P09 Runtime, P10 Minimal UI — M0 v0.1 whole-universe futures, P11 full terminal, P12-P22 + P99)
