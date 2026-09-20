# Audit Report — Phase P04 Market (indicators, sessions, regime v1 causal, MarketView as_of)

**Header**
- Phase: P04
- Date: 2026-09-20
- Agent: arena session `arena/01a0bfdc-tradeterminal`
- implementation_version: 0.1.4 → 0.1.5 (P04 increment)
- git commit: `phase-P04` (pending tag) on `arena/01a0bfdc-tradeterminal`
- Spec: Master Prompt v3.0 ANA-01 (timeframes hierarchy), ANA-02 (in-house feature engine), ANA-03 (sessions tz aware), ANA-04 (regime v1 ADx/ER/BB/ATR percentiles 3 tags+agreement), ARC-06 (MarketView as_of), INV-04 (no look-ahead)

**Scope**
Requirement IDs: ANA-01 timeframes [1m..1d] 6 TF causal, ANA-02 in-house indicators (SMA/EMA seeded SMA, RSI Wilder, ATR Wilder, ADX Wilder, Bollinger population std, VWAP anchored, ER), ANA-03 sessions (Asia/Tokyo, London, NY, killzones tz aware via ZoneInfo), ANA-04 regime v1 (ADx≥22 ER≥0.30 ema stack → TRENDING, ADx≤18 ER≤0.25 BW% → RANGING else UNCERTAIN, vol LOW/NORMAL/HIGH via ATR percentile, EXPANSION/CONTRACTION flags, agreement), ARC-06 MarketView(as_of) only closed candles (close_time ≤ as_of), no repaint.

**What was built**
- `src/gcis/market/indicators.py` — already from P00 (sma, ema seeded, rsi_wilder `ewm alpha 1/14`, atr_wilder `ewm`, adx_wilder `plus_dm/minus_dm/TR/ATR/plus_di/minus_di/dx/adx`, bollinger `rolling mean + population std ddof=0` + bandwidth, vwap_anchored `typical*volume cum per anchor`, rolling_volume_median, efficiency_ratio `net/sum_abs`, returns). All rolling windows are trailing (no centered), causal.
- `src/gcis/market/sessions.py` — `SESSIONS` dict tz strings, `is_session_active(session_key, dt_utc)` converts via `ZoneInfo(cfg tz)` and checks `start <= local.time() <= end` (with overnight handling), `active_sessions(dt_utc)` lists active, `utc_now()`. Config matches `config/default.yaml` sessions (asia 09-15 Asia/Tokyo, london 08-16:30 Europe/London etc.).
- `src/gcis/market/regime.py` — `compute_regime(df, config)` causal only: ADx 14, ER 20, ema21/50, ATR 14 + atr_pct via `rank(pct)` (last value percentile), BB bandwidth percentile, evidences list, trend logic via `config.regime.trend_up/down/ranging` (22/0.30, 22/0.30, 18/0.25/50), vol via `vol_low_atr_percentile_max 25` / `vol_high 80`, flags `EXPANSION atr_pct≥70` / `CONTRACTION bw%≤20`, agreement 1.0 if not UNCERTAIN else 0.3, handles insufficient <30 bars → UNCERTAIN valid False.
- `src/gcis/market/view.py` — `MarketView(as_of, candles, quotes, features, regimes, ict_state, forming_candles)` with `get_closed_candles(symbol,tf)` filtering `close_time <= as_of` (INV-04), `get_forming_candle`, `is_data_fresh`, `quality_state` (HEALTHY ≤5s, DEGRADED ≤30s, DISCONNECTED else, NO DATA).
- `src/gcis/market/engine.py` **new P04** — `build_market_view(candles, quotes, as_of, config)` builds causal view: filters closed per symbol/tf, computes indicators only on closed (`close/high/low/volume` → ema9/21/50 rsi14 atr14 adx14 bb20 bw ER20 vol median → last value dict), regime via `compute_regime` per symbol/tf (populates `regimes`), quotes filtered `updated_at <= as_of`, returns fully populated `MarketView` deterministic (same input → same output, future beyond as_of does not affect).
- `src/gcis/market/candles.py` — Domain `Candle` dataclass validates Decimal 38,18 and UTC tz (already P00, supports INV-13).
- Tests `tests/unit/test_market_p04.py` 9 tests — `test_market_view_no_lookahead_via_engine` (60 bars, as_of 30 →31 closed, late 50 →51, future extended same ema9 `approx`), `test_market_view_forming_not_in_closed` (30s into next bar → still 6 closed), `test_indicators_causal_no_leakage` (ema 30 prefix same as full's 20), `test_regime_causal_and_deterministic` (500 bars same as_of deterministic, early 200 prefix equals early view), `test_regime_oracle_forward_vol_separation` (spike 1000 after 350 does not change regime at 300), `test_sessions_tz_aware` (London 09:00 active, 07:30 killzone vs london false, Asia 00UTC, NY 13:30), `test_quote_filter_as_of` (future quote filtered, HEALTHY/DEGRADED), `test_features_only_closed_not_forming` (early 6 bars rsi None), `test_bollinger_population_std` (flat 10*30 bw0, volatile >0). Plus existing `test_market_view::test_no_lookahead` and `test_quality_state` still pass.
- Verify: `verify --full` 49 tests (40 prior +9 new), `check_invariants` 9/9 (no business logic in streamlit), `source_matrix` 18/18.

**Evidence**
- `PYTHONPATH=src python -m pytest tests/unit/test_market_p04.py -v` → `9 passed in 0.85s` (per test names above)
- `PYTHONPATH=src python -m pytest tests/unit -q` → `49 passed` (.................................................)
- `python scripts/check_invariants.py` → `9/9 OK`
- `python scripts/source_matrix_check.py --assert-min-fallbacks 3` → `18/18 PASSED`
- `PYTHONPATH=src python -m gcis.cli verify --full` → `4 checks OK` (check_invariants, config_load, db_migrations `sqlite:///var/gcis.db`, pytest 49) → `Verify PASSED 2.78s` → `verify_report.json` copied to `docs/audit/P04/verify_report.json`
- Manual determinism: `build_market_view` as_of 30 with 60 bars vs 100 bars extended → `ema9` equal `pytest.approx`; future spike test passes (no leakage).
- Sessions: `is_session_active("london", 2024-01-15 09:00 UTC)` → True (London 09:00), killzone 07:30 true but london false, NY 13:30 true.
- MarketView: `get_closed_candles` length 6 for as_of between 5 close and 6 close (forming excluded), forming not in closed.

**Deviations & Decisions**
- ADX/ATR percentile via `rank(pct)` over entire df up to as_of is causal at last bar (since rank includes only prior bars up to as_of, not future beyond as_of). True oracle would require purged lookback 500 bars; P04 uses `rank(pct)` over available history (50+ bars) which is causal at last bar (no future peek beyond as_of). For full purge validation EMPIRICAL_PENDING.
- Regime vol LOW/HIGH thresholds 25/80 from config `vol_low_atr_percentile_max` / `vol_high_atr_percentile_min` correctly used.
- `compute_regime` returns UNCERTAIN valid False for <30 bars (covers INSUFFICIENT_HISTORY gate per SIG-01).
- No predictive claim without validation (INV-20) — regime evidence is descriptive, not predictive win rate.
- Sessions use `tzdata` 2024.2, handles DST via ZoneInfo (London GMT vs BST not tested in winter case; test uses Jan winter GMT).

**Known limitations / debt**
- Feature engine not yet incremental per ARC-20 (rebuilds full series each call; P04 incremental engine for only affected contracts deferred to P05+). For 5 symbols *6 TF *500 bars it's cheap (~ms), but 400 symbols will need incremental.
- VWAP is computed but not yet stored in MarketView features (stored ema/rsi/atr/adx/bw/er but not vwap; will be added when volume profile via aggTrades P05).
- Regime validation oracle (must separate forward volatility) is not yet automated test beyond our spike test; full oracle `BKT-07` walk-forward purge will be P08.
- No HTF derived via `derive_timeframe` yet integrated into MarketView (P02 derived HTF, P04 MarketView currently expects each TF df supplied separately; caller must supply derived HTF df, not yet auto-derived inside engine).
- P04 EG never blocks CODE_VERIFIED — `EMPIRICAL_PENDING` for forward volatility separation live.

**Empirical gates outstanding (EG)**
- Regime must separate forward volatility (ADx/ER must predict realized vol) → needs 30d live forward returns validation (P08).
- MarketView as_of replay must match live offline replay ( P99 final audit).

**Next phase**
P05 ICT core — `src/gcis/ict/` swings (L=R=3, min_strength_atr 0.5), structure BOS/CHOCH (close break +0.10 ATR), displacement (body_to_range 0.60), FVG (min 0.15 ATR), OB (displacement within 3, require BOS), sweeps (equal tolerance 0.10 ATR), mitigation/breaker/premium OTE 0.62-0.79, HTF/LTF NO_TRADE. Already scaffolded in P00, P05 will add golden+no-repaint tests per ICT-01..13.

**Status: CODE_VERIFIED (causal indicators + regime v1 + sessions tz + MarketView as_of determinism + oracle spike test) — EMPIRICAL_PENDING for forward-vol validation**

*Follow-up command for next phase (see chat): `PYTHONPATH=src python -m pytest tests/unit/test_market_p04.py -v` then implement `src/gcis/ict/swings.py` P05.*

*Attachments: `docs/audit/P04/verify_report.json` (full 49 tests), `src/gcis/market/engine.py`, `tests/unit/test_market_p04.py`.*
