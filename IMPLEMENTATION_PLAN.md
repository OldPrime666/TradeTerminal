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

## P04 Market — CODE_VERIFIED 2026-09-20
- [x] Engine: `src/gcis/market/engine.py::build_market_view(candles,quotes,as_of,config)` — filters closed `close_time <= as_of` (INV-04), computes features only on closed (causal, deterministic), EMA9/21/50 + RSI Wilder + ATR Wilder + ADX Wilder + Bollinger population std + efficiency_ratio + vol median, regime via `compute_regime`, quotes filtered `updated_at <= as_of`, returns `MarketView` with candles/quotes/features/regimes
- [x] Market data already: `market/indicators.py` (sma/ema/rsi_wilder/atr_wilder/adx_wilder/bollinger/bandwidth/vwap/ER), `market/regime.py` (ADX≥22/ER≥0.30/ema stack → TRENDING_UP/DOWN, ADX≤18/ER≤0.25/BW% → RANGING else UNCERTAIN, vol LOW/NORMAL/HIGH via ATR percentile, flags EXPANSION/CONTRACTION), `market/sessions.py` (ZoneInfo tz aware Asia/Tokyo 09-15, London 08-16:30, NY 08:30-17 + killzones 07-10), `market/view.py` (MarketView as_of filtering), `market/candles.py` (Domain Candle Decimal/UTC)
- [x] Tests: `tests/unit/test_market_p04.py` 9 tests — `test_market_view_no_lookahead_via_engine` (31 closed at 30, future not visible, future extended same ema9), `test_market_view_forming_not_in_closed` (30s into next bar → still 6 closed), `test_indicators_causal_no_leakage` (ema/rsi/atr past unchanged), `test_regime_causal_and_deterministic` (same df same regime, prefix regime equals early view), `test_regime_oracle_forward_vol_separation` (future spike 1000 after 350 does not change regime at 300), `test_sessions_tz_aware` (London 09:00 active, killzone 07:30, Asia 00UTC, NY 13:30), `test_quote_filter_as_of` (future quote filtered, HEALTHY/DEGRADED), `test_features_only_closed_not_forming` (early 6 bars rsi None), `test_bollinger_population_std` (10*30 flat bw0, volatile >0)
- [x] Verify: `verify --full` PASSED 49 tests (9 new market p04 +40 prior), `check_invariants` 9/9, `source_matrix` 18/18
- Next: tag `phase-P04` commit, advance BUILD_STATE to P05

## P05 ICT core — CODE_VERIFIED 2026-09-20
- [x] Swings L=R=3, min_strength_atr 0.5, min_separation 3, UTC confirmation, keep-first (no repaint) — `src/gcis/ict/swings.py` with strength filter + separation + causal p+R
- [x] Structure BOS/CHOCH (close +0.10 ATR, bias UNDEFINED→2H+2L, eligible only if confirmation<=bar, UTC-aware, BROKEN) — `src/gcis/ict/structure.py` fixed naive/aware bug + deterministic flip
- [x] Displacement body/range 0.60, range≥1.5 ATR, close 0.70 (bull upper / bear lower) — `src/gcis/ict/displacement.py` + close_position logic
- [x] FVG gap≥max(0.15 ATR,2 ticks) + displacement i-1, zone [high[i-2],low[i]], size_atr, FRESH — `src/gcis/ict/fvg.py` with tick 0.01, 50pct_or_full deferred to mitigation
- [x] OrderBlock last bearish within 3 of displacement+BOS, body zone, max_age 300, require_bos — `src/gcis/ict/order_blocks.py` with disp window + BOS linkage + body zone
- [x] Sweeps equal tolerance 0.10 ATR min 2 touches lookback 100, penetration 0.05 ATR, wick + close back, displacement 3, fallback 20-bar rolling — `src/gcis/ict/sweeps.py` fixed small-n lookback + fallback, equal level clustering causal
- [x] Mitigation FVG/OB (FVG 50pct or full, OB mid+disp, max_age 200/300, TOUCHED/MITIGATED/INVALIDATED) — `src/gcis/ict/mitigation.py` forward scan causal
- [x] Breaker Blocks lookahead 50, buffer 0.10 ATR, flips direction on break of mitigated OB — `src/gcis/ict/breaker.py`
- [x] Premium/Discount OTE 0.62-0.79, eq=(low+high)/2, require_discount/true — `src/gcis/ict/premium.py` + dealing range 20 bars
- [x] HTF/LTF NO_TRADE policy — `src/gcis/ict/htf.py` check alignment
- [x] ICT-11 relative units, ICT-13 docs==code — `docs/ICT_DEFINITIONS.md` mirrors config/default.yaml + code thresholds
- [x] Tests `tests/unit/test_ict_p05.py` 13 tests: swings golden+no-repaint (pivot3 + prefix + oracle spike), structure BOS/CHOCH golden+causal, displacement golden+no-repaint, FVG golden+no-repaint+relative, OB golden requires BOS/disp, sweeps equal golden+no-repaint+oracle, mitigation FVG 50pct (MITIGATED/TOUCHED/INVALIDATED), OB mitigation+breaker, premium OTE, HTF NO_TRADE, relative units, docs==code, integration pipeline causal — all 13 passed (total 62)
- [x] Docs `docs/ICT_DEFINITIONS.md` comprehensive per ICT-01..13, traceability updated ICT-01..13 CODE_VERIFIED, verify --full 62 dots
- Next: tag `phase-P05` commit, advance BUILD_STATE to P06

## P06 Strategy & signals — CODE_VERIFIED 2026-09-20
- [x] Gates MV 33 + PX 7 =40 distinct (GateReason 44, SIG-01 30+ ) — `src/gcis/signals/gates.py` with MV checks quality/disconnected/history/contract/spread etc., PX risk/kill/dup/cooldown/reconciliation
- [x] Fusion setup_score 0-100 weighted htf20 liq20 disp15 zone15 regime10 session5 vol5 cost10, grades A85 B70 C55, hash 16, deterministic — `src/gcis/signals/fusion.py` compute_setup_score + fuse picks best eligible, else best ineligible for display, confluence
- [x] Lifecycle state machines DISCOVERED→QUALIFIED→ARMED→TRIGGERED→EXECUTED + BLOCKED/REJECTED/EXPIRED etc., ALLOWED map, terminals no outgoing — `src/gcis/signals/lifecycle.py` can_transition + ttl_for_timeframe
- [x] Identity ULID 26 + dedup window 6 bars (5m30 15m90 1h360) — `src/gcis/signals/identity.py` generate_signal_id ULID + is_duplicate same symbol/dir/tf within window
- [x] TTL expiry per timeframe 5m12→60m 15m8→120m 1h6→360m — `lifecycle.compute_expiry`
- [x] Snapshots deterministic evidence_hash 16, candles tail 5, config_version — `src/gcis/signals/snapshots.py` capture_snapshot
- [x] Signal contract Signal DB 18 cols ULID PK venue/family/type symbol direction timeframe state DISCOVERED setup_score/quality evidence_hash analysis/config version — `src/gcis/persistence/models.py::Signal` + test
- [x] Outcome Tracker every MV-pass net R even risk-blocked, cost 5+2 bps, pessimistic, would_be_blocked_by_risk — `src/gcis/signals/outcome_tracker.py` compute_net_r 1.23 for 100/99/101.5, label PX_BLOCKED vs MV_FAIL
- [x] StrategyResult contract 11 fields — `src/gcis/strategies/base.py` + `STRATEGY_DEFINITIONS.md`
- [x] ICT-A bi-directional LONG/SHORT (config directions [LONG,SHORT]) HTF bias BULL/BEAR, sweep BULL/BEAR, FVG/OB, premium discount/premium, stop 0.25 ATR TP 1.5/3.0 netRR 1.2/2.0 — `src/gcis/strategies/ict_a.py` both directions with helper _evaluate_direction, causal, deterministic
- [x] Docs `docs/STRATEGY_DEFINITIONS.md` STR-01/02 + `docs/SIGNAL_LIFECYCLE.md` SIG-01..08 single source vs code
- [x] Tests `tests/unit/test_signals_p06.py` 10 tests: gates 30+ and mv/px blocked, fusion weights+grades+hash and best eligible both dirs, lifecycle illegal extended 20+ asserts + terminals, TTL 5m60 15m120 1h360, ULID 26 + dedup true within 10m false 31m etc., snapshots deterministic hash, outcome net R 1.23 and risk-blocked, contract fields, ICT-A long+short view crafting (bias 105/106 vs 106/105), DB contract — all 10 passed (total 72)
- [x] Verify --full 72 tests 4 checks OK, check_invariants 8 OK, source_matrix 18/18
- Next: tag `phase-P06` commit, advance BUILD_STATE to P07

## P07 Risk & Paper — CODE_VERIFIED 2026-09-20
- [x] Risk daily `src/gcis/risk/daily.py` RSK-02 `should_reset_daily`, `reset_daily_state`, `compute_daily_loss_pct` incl unrealised, `is_daily_loss_lock` limit 2% — 00:00 UTC reset tested
- [x] Risk manager patched `src/gcis/risk/manager.py` RSK-06 `is_close` early-allow bypass kill/daily lock separate close atomic
- [x] Sizing `risk/manager.py` round-down to step, hard caps 0.5% per trade / 2% daily / 10x leverage HARD — tests RSK-01 03 04
- [x] Kill-switch atomic `src/gcis/persistence/models.py::KillSwitchState` + `risk/manager.py` KILL_SWITCH_ACTIVE gate → BLOCK_NEW_TRADES, close still allowed
- [x] Paper fills conservative `src/gcis/execution/paper.py` EXE-04 `paper_fill_market` no-mid ±tick, `paper_fill_limit` LONG low<=entry-tick SHORT high>=entry+tick 1 tick trade-through, `evaluate_exits` AMBIGUOUS_STOP_FIRST retained
- [x] Positions `src/gcis/execution/positions.py` EXE-05 `open_position/update_position_mark/close_position` Decimal PnL 38,18, realized/unrealised R
- [x] Catch-up `src/gcis/execution/catch_up.py` EXE-06 `catch_up_missing` idempotent `_seen` + `reset_catch_up_state`
- [x] Tests `tests/unit/test_risk_p07.py` 10 tests RSK-01..09 EXE-04..06: hard caps, daily incl unrealised+midnight, sizing round-down, kill-switch atomic separate close, paper conservative no-mid, limit trade-through, ambiguous, positions PnL, catch-up drill, gates+risk integration — all 10 passed (total 82)
- [x] Fix history mock `tests/unit/test_history.py` patch both bulk+loader download_range + both loader+db get_session
- [x] Verify --full 82 tests 4 checks OK (9 invariants SEC-09), source_matrix 18/18
- Next: tag `phase-P07` commit, advance BUILD_STATE to P08

## P08 Backtest — CODE_VERIFIED 2026-09-20
- [x] Fidelity `src/gcis/backtest/fidelity.py` BKT-02 `resolve_exit_pessimistic` stop_first pessimistic (LONG/SHORT both hit → STOP), `FIDELITY_LEVELS` OHLC_APPROXIMATION/TICK_FROM_BAR
- [x] Metrics `src/gcis/backtest/metrics.py` BKT-08 `compute_metrics` 365d win_rate/avg_win/loss/expectancy/pf/max_dd/sharpe_like/total_net/total_R
- [x] Baselines `src/gcis/backtest/baselines.py` BKT-05 4 baselines `baseline_random` (seed 42 jitter, pessimistic, 5bps) `baseline_buy_hold` `baseline_ema_cross` 9/21 causal `baseline_time_shift_placebo` 24/96/288 hashlib + `run_all_baselines`/`verdict_vs_baselines` OUTPERFORMS etc.
- [x] Census `src/gcis/backtest/census.py` BKT-06/10/12 `run_census(symbols,timeframe)` survivorship-aware (Candle not TRADING), per_symbol days, `quality_report` → backtestability OK/GAP/INSUFFICIENT_HISTORY/NO_DATA, TIER NONE(<1000)/TIER_POOLED_ONLY(1000-5000)/TIER_STRATEGY(>5000)+GAP_WARN, effective_sample, regime note
- [x] Engine `src/gcis/backtest/engine.py` BKT-01..04,08,10,12 `run_backtest(symbols,timeframe,start,end,fidelity,df_override)` shared core MarketView incremental causal `df[:i+1]` + `evaluate_ict_a` + gates `evaluate_mv_gates(res,view,symbol,cfg)`/`evaluate_px_gates(res,{},False,False)` + `is_mv_pass`/`is_px_pass`, entry_zone midpoint / invalidation stop / targets[0] per STR-01, pessimistic `resolve_exit_pessimistic` 100 bars else TIME_EXIT, costs 5bps taker (BKT-03) funding 0, lineage cfg sha12 + analysis 0.1.0 + evidence_hash, metrics 365d, baselines 4 + verdict, backtestability, survivorship, census
- [x] CLI `python -m gcis.cli backtest/census` already backed; config `backtest: default_fidelity OHLC_APPROXIMATION same_bar stop_first annualization 365` already in default.yaml
- [x] Tests `tests/unit/test_backtest_p08.py` 10 tests BKT-01..12: fidelity stop_first, costs realism mock 1 trade entry100.5 cost0.10 net2.39, lineage cfg- , baselines 4+verdict, census 1200→TIER_POOLED_ONLY 6000→TIER_STRATEGY, metrics 365, backtestability GAP/INSUFFICIENT/NO DATA, survivorship, same core causal 51 increasing, no_data honest — all 10 passed (total 92)
- [x] Verify --full 92 tests 4 checks OK (9 invariants SEC-09), source_matrix 18/18
- Next: tag `phase-P08` commit, advance BUILD_STATE to P09

## P09 Runtime — CODE_VERIFIED 2026-09-20
- [x] Supervisor `src/gcis/runtime/supervisor.py` P09 OPS-01..04,11 `PROCESSES [transport,analyzer,risk,paper]` 4, `BACKOFF_SCHEDULE [1,2,4,8,16,30,60]` + `next_backoff` jitter -20%..+20% (jitter), `is_crash_loop` >5/10m FAILED, `heartbeat_age_ms`/`should_heartbeat_be_fresh` ≤5s, `Supervisor` record_failure/record_success/check_heartbeats (HEALTHY/DEGRADED/DISCONNECTED) /recover_idempotent (EventOutbox) /handle_command (idempotency_key, KILL_SWITCH)
- [x] Processes `src/gcis/runtime/processes.py` 4 stubs `run_transport/analyzer/risk/paper` each `update_worker_heartbeat` ≤5s
- [x] Commands `src/gcis/runtime/commands.py` wrapper `submit_command`/`submit_kill_switch`
- [x] Health already `src/gcis/runtime/health.py` `compute_health`/`update_worker_heartbeat` reused
- [x] Tests `tests/unit/test_runtime_p09.py` 7 tests OPS-01..04,11: heartbeat 5s, backoff jitter, crash-loop 5/10m, recovery idempotent, command idempotent, 4 processes HEALTHY→DEGRADED→DISCONNECTED — all 7 passed (total 99)
- [x] Verify --full 99 tests 4 checks OK (9 invariants SEC-09), source_matrix 18/18
- Next: tag `phase-P09` commit, advance BUILD_STATE to P10

## P10 Minimal UI — M0 v0.1 — CODE_VERIFIED 2026-09-20
- [x] Streamlit `src/gcis/app/streamlit_app.py` 400+ lines P10: dark navy UIX-12, banner UIX-04 (Mode/Data/Transport, UTC/London/NY, Venue fallback, Coverage), sidebar dynamic ContractRegistry INV-25, kill switch UIX-01 via `submit_kill_switch` idempotency_key uuid + Command, tabs Overview/Scanner/Coin Detail/Risk Center/System Health/Research read-only INV-06 (no execution/risk import, no while True, no session_state trading)
- [x] .bat `start.bat/verify.bat/start.sh/install.sh` thin wrappers ARC-16, UIX-14
- [x] Tests `tests/unit/test_app_p10.py` 8 tests: banner/health, kill switch via command, no session_state, no loop, bat thin, verify --post-install UNVERIFIED_ENV, health, tabs — all 8 passed (total 107)
- [x] Verify --full 107 tests 4 checks OK (9 invariants SEC-09) + verify --post-install PASSED 12s
- Next: tag `phase-P10` commit, advance BUILD_STATE to P11 — **M0 v0.1 CODE COMPLETE (P00-P10 11 phases)**

## P11 Full terminal — NOT_STARTED (next, P1)
- [ ] Multipage Streamlit `src/gcis/app/pages/` overview/coin/charts/Risk Center/Trade Desk per UIX-02,05..13, EXE-02 idempotency

## ... (P12-P99 per PHASES.md v3: P12 Research I, P13 Probability A, P14 Hardening ... + P99)
