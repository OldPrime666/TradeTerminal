# Audit Report — Phase P06 Strategy & signals

**Header**
- Phase: P06
- Date: 2026-09-20
- Agent: arena session `arena/01a0bfdc-tradeterminal`
- implementation_version: 0.1.7
- git commit: 1f6e8ab + working tree (P06 changes)
- Verify command: `PYTHONPATH=src python -m gcis.cli verify --full`

**Scope**
Requirement IDs: STR-01/02, SIG-01..08 (gates MV/PX 30+ reason codes, fusion setup_score 0-100 weighted, state machines signal/order/position, identity+dedup ULID, TTL, snapshots+explainability, contract Signal DB, Outcome Tracker MV-pass net R also risk-blocked). P05 ICT core remains verified. Out-of-scope P07+.

**What was built**
- `src/gcis/signals/gates.py` — MV_GATES 33 + PX_GATES 7 =40 distinct GateReason (3040 values), SIG-01 30+ coverage. MV checks quality_state DISCONNECTED→DATA_DISCONNECTED, STALE→DATA_STALE, plus strategy reason_codes passthrough; PX checks risk_lock BLOCK_NEW_TRADES→RISK_LIMIT, kill_switch→KILL_SWITCH_ACTIVE, duplicate→DUPLICATE_SETUP, cooldown→COOLDOWN_ACTIVE, reconciliation. Functions `evaluate_mv_gates`, `evaluate_px_gates`, `is_mv_pass`, `is_px_pass`, deduped output.
- `src/gcis/signals/fusion.py` — SIG-02 weighted 0-100 `compute_setup_score` parses evidence for htf (20), sweep (20), disp (15), zone (15), regime (10), session (5), vol (5), cost (10) per `config/setup_score.weights` + grades A85 B70 C55 deterministic hash SHA256 16, `fuse` picks best eligible by weighted score, else best ineligible with gates, confluence count, evidence_hash.
- `src/gcis/signals/lifecycle.py` — SIG-03 state map ALLOWED: DISCOVERED→QUALIFIED/REJECTED/BLOCKED/EXPIRED/INVALIDATED, QUALIFIED→ARMED etc., terminals EXECUTED/REJECTED/EXPIRED/CANCELLED/INVALIDATED no outgoing, BLOCKED→QUALIFIED re-qualify, `can_transition` validates enum, `ttl_for_timeframe` 5m12→60m 15m8→120m 1h6→360m, `compute_expiry`.
- `src/gcis/signals/identity.py` — SIG-04 ULID `str(ulid.ULID())` 26-char Crockford time-ordered, `is_duplicate` checks same symbol/direction/timeframe within dedup_window_bars 6 × tf minutes (5m30,15m90,1h360), `normalize_signal_dict`.
- `src/gcis/signals/snapshots.py` — SIG-06 `capture_snapshot` builds dict with captured_at, view_quality, strategy, direction, setup_score, fusion_score/grade, evidence, mv/px gates, candles_tail 5, config_version, evidence_hash SHA256 16 deterministic, `snapshot_to_signal_fields`.
- `src/gcis/persistence/models.py::Signal` — SIG-07 contract 18 cols: signal_id ULID PK, venue/family/type, symbol, direction, primary_timeframe, created_at, expires_at, state DISCOVERED, setup_score/quality, probability/status, expected_r, entry/stop/targets, regime/session, strategy, evidence_hash, analysis_version, config_version.
- `src/gcis/signals/outcome_tracker.py` — SIG-08 `compute_net_r` (entry 100 stop99 target101.5 cost 5+2 bps => 1.23), `label_outcome` MV_FAIL/PX_BLOCKED/PENDING, `tracker_record` for every MV-pass including risk-blocked with would_be_blocked_by_risk flag persisted to `signal_outcomes` unique signal_id.
- `src/gcis/strategies/base.py::StrategyResult` — STR-01 contract 11 fields validated.
- `src/gcis/strategies/ict_a.py` — STR-02 bi-directional ICT-A version 0.1.0, helper `_evaluate_direction` for LONG vs SHORT, HTF bias BULL/BEAR check, setup swings/structure, displacement, sweep (liquidity_cfg outer for equal levels + disp), FVG/OB both directions, premium discount strict via `compute_dealing_range` 20 bars, eq, stop 0.25 ATR TP 1.5/3.0, netRR 1.2/2.0, score weighted, `evaluate_ict_a` evaluates both allowed_dirs and picks best eligible (higher setup_score) else most promising ineligible, respects `strategy.ict_a.directions [LONG,SHORT]`, causal deterministic, both LONG and SHORT tested. Fixed earlier prefix long-only (short missing).
- Docs `docs/STRATEGY_DEFINITIONS.md` STR-01/02 (version, contract, bi-directional flow) and `docs/SIGNAL_LIFECYCLE.md` SIG-01..08 single source thresholds.
- Tests `tests/unit/test_signals_p06.py` 10 comprehensive + prior `test_signals.py` 2 → total 12 signal tests.
- Config: `config/default.yaml` already has signal TTL/dedup/weights, strategy directions, costs; unchanged.

**Evidence**
- Command: `PYTHONPATH=src python -m pytest tests/unit/test_signals_p06.py -v` → 10 passed 0.61s — gates 30+ (40 distinct, MV DISCONNECTED, PX RISK/KILL/DUP), fusion full evidence score 70+ and ineligible capped 45 and both dirs LONG pick, grades, hash deterministic, lifecycle 20+ illegal asserts (DISCOVERED→EXECUTED false etc., terminals no outgoing, unknown false), TTL 5m60 15m120 1h360 and past 61m expired, ULID 26 and dedup 5m 10m true 31m false diff symbol/direction false 15m 80m true, snapshots hash 16 deterministic diff evidence diff hash, outcome net R LONG 1.23 SHORT 1.23 invalid None MV_FAIL/PX_BLOCKED with risk true, tracker_record, contract 11 fields, ICT-A long view 60 bars craft and short bearish bias craft both return evidence>0, DB contract 9 cols.
- Command: `PYTHONPATH=src python -m pytest tests/unit -q` → `........................................................................` 72 passed (62+10) 9.2s.
- Command: `python scripts/check_invariants.py` → 8 OK (INV-01 06 21 13 15 23 25 26 SEC-09) importlinter warn missing.
- Command: `python scripts/source_matrix_check.py` → 18/18 PASSED.
- Command: `PYTHONPATH=src python -m gcis.cli verify --full` → 4 checks OK (check_invariants, config_load, db_migrations, pytest 72 dots `........................................................................`) Verify PASSED 9.7s → `verify_report.json` + `docs/audit/P06/verify_report.json` (72 dots).
- Artifact: `docs/STRATEGY_DEFINITIONS.md` lists contract + bi-dir flow, `docs/SIGNAL_LIFECYCLE.md` lists MV 33 PX 7 weights grades states etc., traceability updated STR-01/02 SIG-01..08 CODE_VERIFIED.

**Deviations & Decisions**
- ulid API fix: `ulid.new()` not exists in python-ulid 1.1.0 → `str(ulid.ULID())` 26-char, tests updated.
- compute_net_r expectation 1.4-1.6 was miscalc (cost 0.12 not 0.012) → corrected to 1.2-1.4 with net 1.23, test updated.
- ICT-A originally long-only; extended to bi-directional per config directions [LONG,SHORT] via `_evaluate_direction` helper; premium logic now strict `is_discount`/`is_premium` via `compute_dealing_range` and returns MARKET_REGIME_INCOMPATIBLE if fails (strategy then blocked by gate).
- OrderBlocks call in ict_a previously passed `{}` missing displacement; updated to pass `ict_cfg.get("order_block",{})` + `atr_series` + `displacement_indices` for correct OB creation.
- Sweep config for ict_a previously `ict_cfg.get("liquidity",{}).get("sweep",{})` lost equal tolerance outer; changed to pass `liquidity_cfg` outer (contains equal_level_tolerance etc.) to `detect_sweeps`.
- Fusion previously trivial single-strategy max setup_score; upgraded to weighted `compute_setup_score` with evidence parsing to meet 0-100 weight spec and produce deterministic hash.

**Known limitations / debt**
- Fusion volume_confirmation 5 pts still heuristic (always half if eligible, full if "volume" in evidence) — P12 will add real volume profile from aggTrades.
- Probability gate SIG-08 display gate not yet enforced (PRB-01..12 P13) — outcome tracker records net R regardless, probability_status NOT_REQUIRED for paper.
- Lifecycle order/position state machines still minimal (signal only) — P07 will add OrderState + PositionState transitions.

**Empirical gates outstanding (EG)**
- Census tier for strategy after 180d walk-forward (needs P08 backtest + P12).
- Live paper-vs-backtest consistency 30d wall-time (needs P09 runtime).

**Next phase**
P07 Risk & Paper — implement `risk/manager.py` hard caps 0.5/2/10, daily state 00:00 UTC incl unrealised, sizing round down, kill switch, paper fills conservative, positions, catch-up ; update `BUILD_STATE.json current_phase=P07`.

**Status: CODE_VERIFIED (72 tests, 8 invariants, 18 caps) — EMPIRICAL_PENDING for EG census — DOCS==CODE verified**

*Format Part 13.3; evidence at `docs/audit/P06/verify_report.json`.*
