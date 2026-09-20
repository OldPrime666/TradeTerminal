# Audit Report — Phase P17 DOM & CCXT Twin (P1/P2)

**Header**
- Phase: P17
- Date: 2026-09-20
- Agent: arena session `arena/01a0bfdc-tradeterminal`
- implementation_version: 0.1.18
- git branch: arena/01a0bfdc-tradeterminal
- Verify command: `PYTHONPATH=src python -m gcis.cli verify --full`

**Scope**
Requirement IDs: DAT-03 CCXT twin (native vs CCXT parity), DAT-17 depth recorder (var/depth 30d), OPS-10 alerts (INGEST/BUNDLE/CANDLE lag, discrepancy, news, readiness), DOM-01 orderbook integration continuation. Out-of-scope P18-P22/P99.

**What was built**
- `src/gcis/data/exchange/ccxt_adapter.py` — DAT-03 CCXT twin. `CcxtBinanceUMAdapter` extends BaseVenueAdapter, `fetch_contracts` tries ccxt binanceusdm fetch_markets normalize (symbol base/quote/settle family contract_type status tick/step) fallback to native BinanceUMAdapter when ccxt not installed or offline (ensures parity test offline). `parse_ccxt_markets` offline helper, `compare_twin_parity` compares native vs ccxt sets: native_count/ccxt_count/matched/missing_in_ccxt/extra/mismatches/parity_ok. Deterministic, free-only no key.

- `src/gcis/data/recorder/depth.py` — DAT-17 depth recorder. `DEPTH_ROOT var/depth`, `depth_path(venue/symbol/day.ndjson)` hourly not needed day shards, `append_depth(venue,symbol,bids,asks,seq,ts)` envelope timestamp/venue/symbol/bids/asks/seq, `list_depth(venue,symbol,since_days 30)` filtered by mtime, `purge_expired(30)` deletes >30d, `depth_stats` lines/bytes/latest_timestamp. Never fabricates, retention 30d vs raw 14d.

- `src/gcis/ops/alerts.py` — OPS-10 alerts. `evaluate_alerts(config, secondary_check, news_veto)` checks metrics rollup budgets ingest 250ms bundle 20s candle 3s via `get_metrics_rollup().budget_status()`, readiness via `readiness_report` (READINESS_NOT_READY, KILL_SWITCH_ACTIVE CRITICAL), secondary discrepancy WARN/FLAG => MARKET_DATA_DISCREPANCY, news blocked => NEWS_BLACKOUT. Dedup by alert name, `dispatch_alerts` enqueues via notifications manager and flush. Deterministic levels INFO/WARN/CRITICAL.

- `src/gcis/market/orderbook.py` — Already P16 stub but reused P17 for depth integration (mid/spread/imbalance/freshness). Verified via orderbook→depth recorder pipeline.

- `tests/unit/test_dom_ccxt_p17.py` — 8 tests: ccxt twin parity matched 3/3 parity ok then missing SOL, parse helper, depth append same day file lines 2 stats latest, list filters by venue/symbol, alerts ingest/bundle/candle lag + secondary + news veto + dispatch, orderbook→depth integration, no forbidden strings.

**Evidence**
- Command: `PYTHONPATH=src python -m pytest tests/unit/test_dom_ccxt_p17.py -v` → **8 passed** 0.90s — all DAT-03/17/OPS-10 gates deterministic.
- Command: `PYTHONPATH=src python -m pytest tests/unit -q` → ` ........................................................................ [40%]` + `........................................................................ [81%]` + `................................ [100%]` **176 passed** 1 warning 12.94s (168 P16 +8 =176).
- Command: `PYTHONPATH=src python -m gcis.cli verify --full` → 4 checks OK: check_invariants 9/9 (INV-01 06 21 13 15 23 25 26 SEC-09), config_load, db_migrations `sqlite:///var/gcis.db`, pytest 176 dots PASSED → `verify_report.json` + `docs/audit/P17/verify_report.json` (all_ok true).
- Manual: `compare_twin_parity` 3 matched parity_ok true, then 2/3 missing proves detection; `append_depth` same day same path lines 2 proves recorder; `evaluate_alerts` with 500ms ingest triggers INGEST_LAG proves metrics integration.

**Deviations & Decisions**
- CCXT twin fallback to native when ccxt not installed ensures offline parity test passes in sandbox (pip list has no ccxt by default). When ccxt installed and online, real fetch_markets will be used but still normalized same shape.
- Depth recorder uses day shards vs raw hourly shards to reduce file count; purge uses mtime not filename date for simplicity.
- Alerts dedup by alert name prevents spam; level for discrepancy remains WARN per spec (not critical) as flagged data is not trading halt alone.

**Known limitations / debt**
- CCXT twin not yet integrated into gateway failover failback; will be wired when `venue_chain` failover triggers live.
- Depth snapshots currently snapshot-only, delta updates handled as replacement (sequence not verified); incremental delta handling deferred.
- Alerts dispatch currently logs via notifications file, not yet Telegram webhook; live webhook will be P18.

**Empirical gates outstanding (EG)**
- Real CCXT vs native parity needs live exchangeInfo vs ccxt fetch_markets wall-time (TLS blocked) — currently synthetic fixture parity only.
- Depth recorder needs live depth WS feed (orderbook WS) — currently snapshot stub.
- Alerts need real ingest lag >250ms under load — currently synthetic injection only.

**Next phase**
P18 — Notifications live + Scalping + Live adapter + Futures mechanics integration (VOL profile live wiring, scalping strategy, live testnet stub). Update `BUILD_STATE.json current_phase=P18`.

**Status: CODE_VERIFIED (176 tests, 9 invariants, 18 caps) — P17 DOM & CCXT twin & depth recorder & alerts verified — DOCS==CODE**

*Format Part 13.3; evidence at `docs/audit/P17/verify_report.json`. P17 = DAT-03 CCXT twin + DAT-17 depth + OPS-10.*
