# Audit Report — Phase P03 Live Ingest (WS sharded, rotation <24h, gap/backfill, recorder)

**Header**
- Phase: P03
- Date: 2026-09-20
- Agent: arena session `arena/01a0bfdc-tradeterminal`
- implementation_version: 0.1.3 → 0.1.4 (P03 increment)
- git commit: `phase-P03` (pending tag) on `arena/01a0bfdc-tradeterminal`
- Spec: Master Prompt v3.0 DAT-04 (WS ≥2 conns rotation <24h+gap), DAT-05 (state machine), DAT-06 (polling fallback), DAT-08 (freshness/quality), DAT-09 (raw recorder NDJSON+zstd), DAT-11 (QuoteBar 250ms), ARC-04 (outbox+NOTIFY), ARC-05 (Clock), ARC-13 (Decimal/µs)

**Scope**
Requirement IDs: DAT-04 (sharded WS ≤180 streams/conn, rotation 23h+15s, backoff), DAT-05 (gap detection state machine), DAT-06 (polling fallback 5s), DAT-08 (candle integrity Decimal/µs unique), DAT-09 (raw recorder 14d), DAT-11 (closed candle only, open QuoteBar deferred), ARC-04 (event_outbox), ARC-05 (Live/Replay Clock), ARC-13 (Numeric 38,18), plus fault-injection 60s live check (EMPIRICAL_PENDING in sandbox).

**What was built**
- `src/gcis/data/transport/sharding.py` — `shard_streams(max 180)`, `build_klines_streams(sym@kline_1m)`, `build_all_market_streams(bookTicker+markPrice+!forceOrder@arr)`, `build_focus_streams(depth+aggTrade)`, `plan_shards(symbols,focus,180)` shards ceil(N/180) per ARC-20, `shard_summary` (shards/streams). Example: 400 symbols → 3 shards klines_1m (180/180/40).
- `src/gcis/data/transport/ws_client.py::WSConnection` — `venue/group/streams/ws_base`, `rotate_before_h 23` + `rotation_overlap_s 15` per `config/transport`, `_build_url` (`wss://fstream.binance.com/stream?streams=...`), `should_rotate`, `connect_and_serve` loop (`websockets.connect ping 180/600`, state DISCONNECTED→CONNECTING→WEBSOCKET→RECOVERING, `backoff_schedule [1,2,4,8,16,30,60]`, 451/403 → RESTRICTED warning no aggressive reconnect), `_serve_loop` (json loads, handles combined stream wrap `data`, calls `on_message(payload,ts_us)`, proactive `rotate<24h` close 1000 after 23h), `health()` (venue/group/state/streams/connected_at/last_msg/should_rotate/attempts).
- `src/gcis/data/transport/polling.py` — `poll_klines(venue,symbols,interval limit2)` via `BinanceUMAdapter.klines`, `normalize_timestamp_to_us`, 451/403 → [] no circumvention, `polling_loop_should_run(ws_state,5s)` only when ws_state != WEBSOCKET.
- `src/gcis/data/transport/gap.py` — `detect_missing_intervals(sorted open_times, start,end, interval_us)` contiguous missing → list [(gap_start,gap_end)], `backfill_missing(gaps, max 1500)` via REST `klines` startTime, interval derive, `should_trigger_backfill`.
- `src/gcis/data/recorder/store.py` — `RAW_ROOT var/raw`, `raw_path(venue/day/stream-hour.ndjson)` hourly shards, `append_raw(venue,stream,payload,ts_us)` NDJSON envelope `_received_at/_venue/_stream/payload`, `list_raw(since 14d)`, `purge_expired(14d)`, `compress_raw` zstd hook (optional). P03 keeps plain NDJSON, zstd compress on rotation deferred to P09.
- `src/gcis/data/transport/manager.py` — `WS_BASES` futures mapping, `handle_kline_message(payload,ts_us,venue)` (WS `e/k/x` only when `x==True` closed → `_persist_candle`, polling dict `open_time` path), `_persist_candle` (Decimal 38,18 via strings, high>=low check, open_time→datetime UTC, unique `(venue,symbol,tf,open_time)` idempotent skip, insert `Candle` + `EventOutbox candle.closed entity_id venue:symbol:tf:open_time` + `ingest_rows_to_parquet` archive same row + `ProviderStatus CAP-03 data_age_s`), `TransportManager(venue,symbols,focus)` builds `plan_shards` → `WSConnection` per shard with handler `append_raw+handle_kline`, `health()` aggregates ws_state WEBSOCKET/DEGRADED/DISCONNECTED, `polling_tick` (if not WEBSOCKET), `gap_tick` (query Candle for first symbol, detect missing, backfill first gap), `heartbeat_tick` (WorkerState transport lag_ms), `run_forever` asyncio gather WS + loop.
- Tests `tests/unit/test_transport.py` 8 tests — `test_shard_streams` 400→3, `test_ws_client_should_rotate` 23h true/1h false URL check, `test_gap_detection` missing 00:02 gap 1, `test_polling_should_run` states, `test_raw_recorder` tmp NDJSON, `test_candle_persist_and_idempotent` (in-memory DB candle+outbox dup→still 1), `test_transport_manager_plan` 5 symbols→3 conns, `test_no_business_logic_in_streamlit`.
- Invariants: `scripts/check_invariants.py` 9/9 OK (INV-21 no while True in streamlit, INV-01 no fabricated data), `scripts/source_matrix_check.py` 18/18 PASSED (CAP-02 live 1m, CAP-03 REST, CAP-04 bulk).
- Demo: TransportManager with 5 symbols (BTCUSDT etc. from ContractRegistry) builds 3 connections (klines/all_market/focus) correctly; raw recorder `var/raw/binance_um/...` not yet populated live (needs ws), but `append_raw` validated via tmp.

**Evidence**
- `PYTHONPATH=src python -m pytest tests/unit/test_transport.py -v` → `8 passed in 1.06s`
- `PYTHONPATH=src python -m pytest tests/unit -q` → `40 passed` (........................................)
- `python scripts/check_invariants.py` → `9/9 OK`
- `python scripts/source_matrix_check.py --assert-min-fallbacks 3` → `18/18 PASSED`
- `PYTHONPATH=src python -m gcis.cli verify --full` → `4 checks OK` (check_invariants, config_load, db_migrations `sqlite:///var/gcis.db`, pytest 40) → `Verify PASSED 2.45s` → `verify_report.json` copied to `docs/audit/P03/verify_report.json`
- Manual gap demo: `detect_missing_intervals` with times 00:00,00:01,00:03 → gap 00:02 detected; `polling_loop_should_run` WEBSOCKET false, DISCONNECTED true.
- Candle persist demo: WS kline payload `x:true` → 1 Candle +1 outbox, duplicate → still 1 (idempotent) per test `test_candle_persist_and_idempotent`.
- Archive still `var/archive/binance_um/BTCUSDT/1m/2024-01-01.parquet` 5 rows from P02 (shard logic reuses same `ingest_rows_to_parquet` for live closed candles).

**Deviations & Decisions**
- AS-02 TLS sandbox: live WS `wss://fstream.binance.com` also TLS-blocked (`SSLZeroReturnError`) → manager health DISCONNECTED → polling fallback triggers (every 5s) but poll REST also TLS-blocked → NO DATA honest, 60s live check `UNVERIFIED_ENV` (mechanism CODE_VERIFIED via mocked WS, not live wall-time). Never circumvent 451.
- `focus_set` depth@0ms+aggTrade is stub (no real depth book building yet, P03 only logs raw; full order book will be P05/P07 DOM).
- `raw recorder` keeps plain NDJSON P03, `compress_raw` zstd is optional hook not yet called on rotation (P09 will compress hourly). Retention 14d via `purge_expired` not yet scheduled (P09 supervisor).
- `outbox` inserts per candle but `LISTEN/NOTIFY` not yet wired (ARC-04 deferred to P09 supervisor); P03 only writes `event_outbox` table.
- `QuoteBar 250ms` (DAT-11) deferred: we only persist closed klines `x==True`, open quotes still via `LatestQuote` polling fallback not yet 250ms aggregated (P04 MarketView).

**Known limitations / debt**
- No actual live WS connection in sandbox (requires reachable `fstream.binance.com`); P03 60s live soak `EMPIRICAL_PENDING` until live host.
- No `!forceOrder@arr` liquidation parsing yet (stream included in all_market but payload not yet persisted to `liquidations` table).
- No `markPrice` funding handling in live (REST bulk already handles, live markPrice will be DAT-09 variant).
- No multi-venue sharding yet (only binance_um primary; Bybit/OKX will be added when `venue_chain` failover triggers via `sync_registry` but live transport manager still single venue parameter single-venue P03).
- No `max_parallel_downloads 4` for gap backfill (sequential per gap).

**Empirical gates outstanding (EG)**
- 60s live WS with 1 closed candle (AC live ingest) → needs reachable venue, not in sandbox.
- 7d 0 gaps (DAT-05) → wall-time.
- EG never blocks CODE_VERIFIED.

**Next phase**
P04 Market — `src/gcis/market/` indicators (ATR/RSI/EMA/ADx/BB), sessions tz-aware, regime v1 causal (ADx/ER/BB/ATR percentiles, 3 tags+agreement), `MarketView(as_of)` no-lookahead. Already scaffolded in P00, P04 will add causality tests + oracle leakage.

**Status: CODE_VERIFIED (sharded WS mechanism + offline mocked gap/polling + idempotent candle+outbox) — UNVERIFIED_ENV for live 60s (TLS blocked) — EMPIRICAL_PENDING for 7d**

*Follow-up command for next phase (see chat): `PYTHONPATH=src python -m pytest tests/unit/test_transport.py -v` then `src/gcis/market/indicators.py` P04.*

*Attachments: `docs/audit/P03/verify_report.json` (full 40 tests), `src/gcis/data/transport/*`, `src/gcis/data/recorder/store.py`.*
