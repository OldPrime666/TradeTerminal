# Audit Report — Phase P18 Live & Futures + Scalping (P2/P3)

**Header**
- Phase: P18
- Date: 2026-09-20
- Agent: arena session `arena/01a0bfdc-tradeterminal`
- implementation_version: 0.1.19
- git branch: arena/01a0bfdc-tradeterminal
- Verify command: `PYTHONPATH=src python -m gcis.cli verify --full`

**Scope**
Requirement IDs: FUT-01..09 (futures mechanics: liquidation/mark, buffer 0.5+1ATR, funding, inverse PnL, lifecycle, leverage), LIVE-01..10 (live adapter off by default, testnet, idempotency, reconciliation), STR-SCALPING (scalping mean-reversion on 1m with volume profile + orderbook). Out-of-scope P19-P22/P99.

**What was built**
- `src/gcis/futures/mechanics.py` — FUT-01..09. `calc_liquidation_price(entry, leverage, side, mmr)` LONG liq = entry*(1 - (1/lev - mmr)), SHORT opposite. `check_liquidation_buffer(entry,stop,liq,atr, max_stop 0.5, buffer 1.0)` checks |entry-stop|<=0.5*|entry-liq| and |stop-liq|>=ATR. `funding_cost_estimate(rate, notional, 8h)` per_interval+per_day, `inverse_pnl` vs `linear_pnl` distinct, `effective_leverage`, `contract_lifecycle` ACTIVE/EXPIRING_SOON/CLOSE_REQUIRED/EXPIRED per expiry + close_before_delivery 2h min 12h, `market_beta_cluster_risk` stub MARKET_BETA. Decimal where needed.

- `src/gcis/execution/live_adapter.py` — LIVE stub. `LiveAdapter` reads `app.enable_live_trading` false default (LIVE-01), testnet flag, `submit_order` requires idempotency_key >=8 and exchange-resident stop advisory, idempotency_store dedup (EXE-02), `_require_enabled` gate, `cancel_order`, `fetch_positions`, `reconcile` comparing local vs exchange drift (LIVE-09). All methods return LIVE_DISABLED when disabled. `get_live_adapter` helper.

- `src/gcis/strategies/scalping.py` — Scalping 1m. `evaluate_scalping(view,symbol,config)` timeframe 1m lookback 20, volume profile via `compute_volume_profile` 24 bins 70% VA, orderbook `get_book` imbalance threshold 0.3, entry zone close±0.1ATR stop beyond VA ±0.5ATR or 0.8ATR, tp to POC or 1.2R, cost 5+2 bps, score 50+imbalance 10+distance 15+netR 5 max 85 min_score 55, quality gate. Version 0.3.0.

- `src/gcis/futures/__init__.py` — package marker.

- `tests/unit/test_live_scalping_p18.py` — 6 tests: futures liquidation long<entry<short + buffer pass/fail + funding 1/3 per_day + inverse vs linear + lifecycle ACTIVE/EXPIRED/CLOSE_REQUIRED + market beta, live adapter disabled/idempotency duplicate/missing key/cancel/reconcile drift, scalping strategy eligible with VA+imbalance and disabled, insufficient history, no forbidden strings.

**Evidence**
- Command: `PYTHONPATH=src python -m pytest tests/unit/test_live_scalping_p18.py -v` → **6 passed** 0.32s — all FUT/LIVE/scalping deterministic.
- Command: `PYTHONPATH=src python -m pytest tests/unit -q` → ` ........................................................................ [39%]` + `........................................................................ [79%]` + `...................................... [100%]` **182 passed** 1 warning 12.87s (176 P17 +6 =182).
- Command: `PYTHONPATH=src python -m gcis.cli verify --full` → 4 checks OK: check_invariants 9/9 (INV-01 06 21 13 15 23 25 26 SEC-09), config_load, db_migrations `sqlite:///var/gcis.db`, pytest 182 dots PASSED → `verify_report.json` + `docs/audit/P18/verify_report.json` (all_ok true).
- Manual: `calc_liquidation_price` 100 3x long ~67 <100<~132 short proves liquidation; `inverse_pnl` vs `linear_pnl` differ proves inverse; `LiveAdapter` disabled returns LIVE_DISABLED then enabled dedup proves idempotency.

**Deviations & Decisions**
- Liquidation calc simplified linear proxy with mmr 0.01 and 0.9 factor, sufficient for buffer gate testing; exchange precise formula with tiered MMR will be refined when live margin tiers fetched.
- Funding estimate per_interval linear, not compounding; per-day = per_interval*3 for 8h interval.
- Scalping volume profile uses candles not aggTrades tick data (tick-level profile deferred to P19 with DAT-16 trade archive).
- Live adapter testnet flag true but live disabled by default; reconciliation stub uses empty exchange positions when offline.

**Known limitations / debt**
- Live adapter not yet connected to real Binance testnet REST (fapi testnet); will be wired when `live_adapter` real client added.
- Futures margin tiers (FUT-02 tiers notional thresholds) not yet dynamic per symbol; uses fallback mmr 0.01.
- Scalping real orderbook imbalance requires live depth WS; currently snapshot stub.
- Inverse PnL multiplier fixed 1.0; contract spec multiplier (e.g., 100 for inverse) deferred.

**Empirical gates outstanding (EG)**
- Real liquidation price needs live mark price + MMR tier (exchangeInfo) wall-time — currently synthetic calc.
- Live adapter end-to-end test requires testnet credentials (never stored in repo) — currently stub with idempotency only.
- Scalping edge needs 1m live ingest 7d wall-time — synthetic tests only.

**Next phase**
P19 — Next (likely remaining hardening / futures inverse live / audit prep). Update `BUILD_STATE.json current_phase=P19`.

**Status: CODE_VERIFIED (182 tests, 9 invariants, 18 caps) — P18 Live & Futures + Scalping verified — DOCS==CODE**

*Format Part 13.3; evidence at `docs/audit/P18/verify_report.json`. P18 = FUT+LIVE+SCALPING.*
