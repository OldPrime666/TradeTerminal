# Audit Report — Phase P05 ICT Core

**Header**
- Phase: P05
- Date: 2026-09-20
- Agent: arena session `arena/01a0bfdc-tradeterminal`
- implementation_version: 0.1.6
- git commit: 73529bf + working tree (P05 changes uncommitted)
- Verify command: `PYTHONPATH=src python -m gcis.cli verify --full`

**Scope**
Requirement IDs: ICT-01..13 (swings L=R=3 min_strength 0.5 separation 3, BOS/CHOCH close 0.10 ATR, displacement body 0.60 range1.5 close70%, FVG 0.15 ATR 2 ticks displacement middle max_age200 50pct, OB displacement3 require_bos body zone max_age300, sweeps equal 0.10 min2 lookback100 pen0.05 reject3 wick+disp, mitigation breaker premium OTE 0.62-0.79 HTF NO_TRADE relative docs==code). Plus ICT-11/13 cross-cutting. Out-of-scope P06+.

**What was built**
- `src/gcis/ict/swings.py` — causal L=R=3 strict left / non-strict right, confirmation p+R, strength prominence/ATR filter 0.5 (skip when ATR NaN warmup), min_separation 3 causal keep-first (no repaint), deterministic, status CONFIRMED→BROKEN, UTC-aware.
- `src/gcis/ict/structure.py` — BOS/CHOCH on close +0.10 ATR, bias UNDEFINED until ≥2H+2L, initial bias from last highs/lows, only confirmed swings eligible (`confirmation_at ≤ bar_time` UTC-aware compare fixed bug), BOS vs CHOCH_BULL/BEAR, marks BROKEN, causal.
- `src/gcis/ict/displacement.py` — `is_displacement` body/range ≥0.60 and range≥1.5 ATR and closePosition≥0.70 (bull upper 70% / bear complement high-close≥0.70), min_consecutive 1, causal per bar. Fixed to include close_position.
- `src/gcis/ict/fvg.py` — 3-bar gap [high[i-2],low[i]] BULL / opposite BEAR, gap≥max(0.15 ATR,2 ticks 0.01), middle must be displacement if indices supplied, zone + midpoint + size_atr, created_index, status FRESH, max_age 200 via mitigation, causal.
- `src/gcis/ict/order_blocks.py` — displacement_within 3, require_bos true, use_body_zone true, max_age 300, last bearish origin before displacement+ BOS within 3, zone body (or full), causal, origin/break indices.
- `src/gcis/ict/sweeps.py` — equal tolerance 0.10 ATR min_touches 2 lookback 100, sweep penetration ≥0.05 ATR + close back inside + displacement within 3, wick_based, causal equal clustering + fallback rolling 20-bar max/min for synthetic, fixed small-n lookback bug (was `max(lookback,20)`).
- `src/gcis/ict/mitigation.py` — FVG mitigation 50pct_or_full (low≤mid or close≤lower) TOUCHED when wick enters upper, age>200→INVALIDATED; OB mitigation 50% + disp away, max_age 300, forward causal scan.
- `src/gcis/ict/breaker.py` — lookahead 50, buffer 0.10 ATR, flips direction when OB broken opposite with displacement, ACTIVE.
- `src/gcis/ict/premium.py` — premium/discount eq=(low+high)/2, OTE long 62-79% retrace from high (97.1-98.8 for 95-105 example) and short opposite, require_discount_for_long/true, relative units.
- `src/gcis/ict/htf.py` — NO_TRADE policy BULL→LONG only, BEAR→SHORT only, UNDEFINED allows.
- `docs/ICT_DEFINITIONS.md` — single source mirroring config/default.yaml thresholds + code, per ICT-01..13.
- Tests `tests/unit/test_ict_p05.py` 13 comprehensive.
- Config unchanged `config/default.yaml` ict block already correct (0.1.6).

**Evidence**
- Command: `PYTHONPATH=src python -m pytest tests/unit/test_ict_p05.py -v` → 13 passed (7.11s) — swings golden pivot3 + prefix subset + oracle spike, structure BOS golden+causal prefix+oracle, displacement golden (bull 0.6 bear 0.8) + no-repaint, FVG bullish gap1 + bearish + causal before-i 0, OB golden requires BOS+disp within3 + no-disp fails + prefix 0, sweeps equal 3 highs 100→ sweepH 100.3 close99.9+disp21 + bull sweep 99.6 close100.5 + no-repaint prefix + oracle, mitigation FVG 50pct MITIGATED/TOUCHED/INVALIDATED, OB mitigation TOUCHED+breaker BEAR, premium OTE zones 97.1-98.8 etc., HTF NO_TRADE 4 combos, relative tiny gap 0.05 filtered vs 1.0 pass, docs_eq_code (swing 3 left right etc.), integration pipeline causal full.
- Command: `PYTHONPATH=src python -m pytest tests/unit -q` → `..................................................` 62 passed (49+13) 9.1s.
- Command: `python scripts/check_invariants.py` → 8 OK (INV-01,06,21,13,15,23,25,26, SEC-09) + importlinter warn (not installed).
- Command: `python scripts/source_matrix_check.py` → 18/18 PASSED (>=3 fallbacks, keyless).
- Command: `PYTHONPATH=src python -m gcis.cli verify --full` → 4 checks OK (check_invariants, config_load, db_migrations, pytest 62 dots) Verify PASSED 9.5s → `verify_report.json` + `docs/audit/P05/verify_report.json` (62 dots `..............................................................`).
- Artifact checks: `docs/ICT_DEFINITIONS.md` contains L=R=3 0.60 0.15 0.62 NO_TRADE etc.; `config/default.yaml` ict thresholds match.
- Determinism: prefix vs full same early swings, structure events 0 before break, FVG not before i, sweep not before 20, oracle spike 1000 after 350 (or 50-high 1000) not affecting early ≤30.
- No hard-coded universe, free-only fallbacks via sources.yaml still 18/18.

**Deviations & Decisions**
- AS-NaiveAware fix: structure compared aware vs naive datetime error (`TypeError can't compare offset-naive and offset-aware`) fixed via `pd.to_datetime(..., utc=True)` helper UTC Timestamp compare + `bar_time_dt` event. Ensures TZ correctness (Asia/Tokyo etc.).
- Sweeps small-n bug: `for i in range(max(lookback,20),n)` skipped when lookback 100 but n=30 (synthetic) → never emitted sweeps; fixed to `range(20,n)` with `window_start=max(0,i-lookback)` to respect lookback while allowing small n causal.
- Displacement strictness: added close_position_min check (was only body/range + range ATR); bulk bearish displacement now checks `(high-close)/range≥0.70` complement.
- FVG & sweeps displacement filter enforcement strict Table: tiny gap test initially failed because middle not displacement; adjusted test data to ensure middle displacement body/range passes.
- Mitigation premature flat background (make_base low 99.5 inside FVG zone) caused immediate MITIGATED before test bar 10; fixed tests to use `start=103` background high 103 >101 to keep FRESH until deliberate touch.
- OB breaker displacement range: builder range 1.2 <1.5 failed displacement; enlarged to 2.5 (high 101 low 98.5) for breaker test.
- Structure test reuse of swings list across calls mutated status → second call empty; fixed test to `copy.deepcopy` swings per call.

**Known limitations / debt**
- ICT detectors still use simple 20-bar dealing range for premium vs swing-derived range; P06 will integrate real swing-derived HTF range per strategy.
- Equal-level clustering O(N·lookback·lookback) ~ 100*30*30=90k per detection, okay for 1500 bars but will need optimization with inversion for whole universe (P06 incremental engine).
- OB `max_cluster` handling of up to 3 consecutive opposite candles not yet tested as cluster; current looks for single last opposite candle within 5 lookback (covers ICT cluster partially).
- Volume confirmation (ICT volume) not yet used in displacement (requires aggTrades volume profile P12).
- Warmup ATR NaN handling skips strength filter; after 14 bars filter applies — documented.

**Empirical gates outstanding (EG)**
- Real market forward sweeps vs equal levels validation 7d wall-time (needs live Binance reachable, currently TLS blocked → UNVERIFIED_ENV for DAT-04 but CODE_VERIFIED via synthetic).
- Census tier for ICT-A after 180d walk-forward (P12).

**Next phase**
P06 Strategy & signals — implement `strategies/ict_a.py` gates/fusion (SIG-01..08) with premium/HTF integration, state machines, dedup/TTL/snapshots, Outcome Tracker ; illegal-transition tests ; update `BUILD_STATE.json current_phase=P06`.

**Status: CODE_VERIFIED (mechanism 62 tests, 8 invariants, 18 source caps) — EMPIRICAL_PENDING for EG live/census — DOCS==CODE verified**

*Format Part 13.3; evidence at `docs/audit/P05/verify_report.json`.*
