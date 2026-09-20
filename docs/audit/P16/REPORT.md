# Audit Report — Phase P16 Scalability ARC-20 (P1)

**Header**
- Phase: P16
- Date: 2026-09-20
- Agent: arena session `arena/01a0bfdc-tradeterminal`
- implementation_version: 0.1.17
- git branch: arena/01a0bfdc-tradeterminal
- Verify command: `PYTHONPATH=src python -m gcis.cli verify --full`

**Scope**
Requirement IDs: ARC-20 (scale design) — 1m base only HTF derived (P02), sharded WS (P03), incremental engine (only affected contracts), prioritised scheduling (landing-scanner-level2+derivatives, in-risk-set), bundle budget 20s → ANALYSIS_LAG (never silent skip), NOT_SUBSCRIBED status. Plus DOM-01 stub preparation. Out-of-scope P17-P22/P99.

**What was built**
- `src/gcis/data/transport/scheduler.py` — ARC-20 prioritised scheduling + bundle budget. `prioritise_symbols` with landing > scanner > level2 > derivatives > in_risk > other, operator_pins promoted to landing, alphabetical within tier deterministic. `schedule_bundles` per_symbol cost 50ms+6*2=62ms, budget 20s (20000ms) => processed vs NOT_SUBSCRIBED, status ANALYSIS_LAG when exceed (never silently skip), `plan_with_priority` combines prioritisation + `plan_shards` + schedule, shard_summary.

- `src/gcis/market/incremental.py` — Incremental engine. `IncrementalEngine` caches as_of+result per symbol:tf, `is_affected` compares latest close_time > last_as_of, `update` returns cached if not affected else recomputed, `bundle_update` batch for prioritised symbols with stats total/affected/skipped, `invalidate`. Only affected contracts recomputed per ARC-20f.

- `src/gcis/market/orderbook.py` — DOM-01 stub (light for P16). `OrderBook` with bids/asks Decimal 38,18, sorted, `apply_snapshot`/`apply_update`, `best_bid`/`best_ask`/`mid_price`/`spread_bps`/`imbalance` top-5, `freshness_status` HEALTHY/STALE/DISCONNECTED/NO_DATA via updated_at 5s/30s, `to_snapshot`, global registry `get_book`/`clear_books`. Prepares for DOM depth recorder incremental.

- `src/gcis/data/transport/sharding.py` — Already existed P03 but reaffirmed P16: ≤180 streams/conn, klines_1m + all_market + focus_set via plan_shards.

- `tests/unit/test_scale_p16.py` — 8 tests: prioritise order landing>scanner>level2>in_risk and operator pins, schedule budget OK vs ANALYSIS_LAG 100 symbols 20s all OK vs 1s 16/84 lag, plan_with_priority integrated, incremental affected/cache/invalidate/bundle, orderbook mid 100.5 spread ~99.5bps freshness stale/disconnected imbalance, sharding 400→3 shards, no forbidden strings.

**Evidence**
- Command: `PYTHONPATH=src python -m pytest tests/unit/test_scale_p16.py -v` → **8 passed** 0.32s — all ARC-20 gates deterministic, no silent skip, cache correct.
- Command: `PYTHONPATH=src python -m pytest tests/unit -q` → ` ........................................................................ [42%]` + `........................................................................ [85%]` + `........................ [100%]` **168 passed** 1 warning 12.82s (160 P15 +8 =168).
- Command: `PYTHONPATH=src python -m gcis.cli verify --full` → 4 checks OK: check_invariants 9/9 (INV-01 06 21 13 15 23 25 26 SEC-09), config_load, db_migrations `sqlite:///var/gcis.db`, pytest 168 dots PASSED → `verify_report.json` + `docs/audit/P16/verify_report.json` (all_ok true).
- Manual: `prioritise_symbols` BTC landing first proves priority; `schedule_bundles` 1s budget gives 16 processed 84 NOT_SUBSCRIBED proves budget; `IncrementalEngine` second same as_of cached proves incremental; `OrderBook` spread 99.5bps proves DOM calc.

**Deviations & Decisions**
- Per-symbol cost fixed 62ms for demo; real engine will measure actual ms via metrics rollup P14. Budget check is deterministic pre-execution estimate.
- Incremental uses latest close_time comparison, not full df hash, to keep low overhead; invalidation explicit via symbol.
- OrderBook delta handling deferred to P17 (currently snapshot replace); shallow estimator sufficient for spread/freshness.
- Sharding still 180 streams/conn per transport config; focus_set derived from in_risk_set for P16 demo.

**Known limitations / debt**
- Incremental cache in-memory only (not persisted); supervisor restart would recompute all — acceptable for P16, persistence deferred.
- DOM depth recorder (DAT-17) not yet persisting to parquet; will be P17.
- Real bundle latency budget enforcement in supervisor loop not yet wired; scheduler provides decision but not yet integrated into transport manager's run loop.

**Empirical gates outstanding (EG)**
- Real 400 symbols WS sharding 3 conns needs live wall-time 60s wall test (TLS blocked) — honest NOT_SUBSCRIBED not yet exercised live.
- Incremental benefit needs 500+ symbols to measure skip savings — synthetic tests only.
- DOM freshness needs live depth WS feed — currently snapshot stub.

**Next phase**
P17 — DOM Depth + CCXT twin + Notifications live wiring (DAT-17, DAT-03 CCXT twin, OPS-10 alerts integration). Update `BUILD_STATE.json current_phase=P17`.

**Status: CODE_VERIFIED (168 tests, 9 invariants, 18 caps) — P16 Scalability ARC-20 prioritised + bundle budget + incremental + DOM stub verified — DOCS==CODE**

*Format Part 13.3; evidence at `docs/audit/P16/verify_report.json`. P16 = ARC-20 scale design.*
