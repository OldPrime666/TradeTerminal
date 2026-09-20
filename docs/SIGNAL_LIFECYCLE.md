# Signal Lifecycle — P06 SIG-01..08

> **Source:** `src/gcis/signals/*.py` + `src/gcis/core/enums.py::SignalState` + `config/default.yaml` signal block. Version `0.1.0`.

## SIG-03 State Machines
States: DISCOVERED → QUALIFIED → ARMED → TRIGGERED → EXECUTED (terminals: EXECUTED, REJECTED, EXPIRED, CANCELLED, INVALIDATED, BLOCKED). BLOCKED can re-qualify → QUALIFIED.
Allowed map per `signals/lifecycle.py::ALLOWED`:
- DISCOVERED → QUALIFIED, REJECTED, BLOCKED, EXPIRED, INVALIDATED
- QUALIFIED → ARMED, BLOCKED, EXPIRED, INVALIDATED, CANCELLED
- ARMED → TRIGGERED, BLOCKED, EXPIRED, INVALIDATED, CANCELLED
- TRIGGERED → EXECUTED, BLOCKED, EXPIRED, INVALIDATED, CANCELLED
- BLOCKED → QUALIFIED, ARMED, EXPIRED, INVALIDATED, CANCELLED
Terminals have no outgoing. `can_transition(frm,to)` enforces; illegal-transition test covers all.

## SIG-01 Gates MV/PX 30+ codes
MV_GATES (33): DATA_STALE, DATA_DISCONNECTED, ORDERBOOK_STALE, CANDLE_DATA_INVALID, CLOCK_DRIFT, MARKET_DATA_DISCREPANCY, INSUFFICIENT_HISTORY, SYMBOL_INVALID, CONTRACT_NOT_TRADING, CONTRACT_SETTLING, UNIVERSE_WARMING_UP, LIQUIDITY_TOO_LOW, SPREAD_TOO_WIDE, FUNDING_TOO_COSTLY, LIQUIDATION_BUFFER_INSUFFICIENT, LEVERAGE_EXCEEDS_CAP, POSITION_DATA_BLIND, VENUE_SWITCH_INVALIDATED, NO_DERIVS_CONTEXT, MARKET_TYPE_VIOLATION, INVALID_STRUCTURE, NO_CLEAR_ENTRY, NO_CLEAR_TARGET, INSUFFICIENT_RR, COST_TOO_HIGH, MARKET_REGIME_INCOMPATIBLE, CONFLICTING_EVIDENCE, HTF_LTF_CONFLICT, SESSION_INACTIVE, NEWS_RISK, NEWS_UNAVAILABLE, STRATEGY_DISABLED, EXECUTION_UNSAFE
PX_GATES (7): RISK_LIMIT, COOLDOWN_ACTIVE, DUPLICATE_SETUP, KILL_SWITCH_ACTIVE, RECONCILIATION_ERROR, SIGNAL_EXPIRED, INSUFFICIENT_PROBABILITY_DATA
Total 40 distinct GateReason values. `evaluate_mv_gates(strategy_result, view, symbol, config)` checks quality_state STALE/DISCONNECTED etc. and maps strategy reason_codes. `evaluate_px_gates(signal, risk_state, kill_switch, duplicate)` checks risk_lock, cooldown, kill, duplicate.

## SIG-02 Fusion setup_score 0-100
Weights `config/setup_score.weights`: htf_alignment 20, liquidity_sweep_quality 20, displacement_quality 15, zone_quality 15, regime_compat 10, session_context 5, volume_confirmation 5, cost_efficiency 10 sum 100. Grades `A85 B70 C55 D`. `compute_setup_score(strategy_result, view, symbol, config)` parses evidence string for each bucket. `fuse(strategy_results, config)` picks best eligible by weighted score, else best ineligible for display, computes evidence_hash SHA256 16 chars, confluence count.

## SIG-04 Identity + Dedupe ULID
`generate_signal_id()` → `str(ulid.ULID())` 26-char Crockford. `is_duplicate(new, existing, dedup_window_bars, timeframe)` checks same symbol/direction/timeframe within window: 6 bars × tf minutes (5m→30m,15m→90m,1h→360m). Config `signal.dedup_window_bars 6`.

## SIG-05 TTL
`ttl_for_timeframe(tf, config)` reads `signal.ttl_bars`: 5m 12→60m,15m 8→120m,1h 6→360m. `compute_expiry(created_at, timeframe, config)` = created_at + TTL. Expiry test covers.

## SIG-06 Snapshots + Explainability
`capture_snapshot(view, symbol, timeframe, strategy_result, fusion_result, mv_gates, px_gates, config)` builds dict with captured_at, view_quality, strategy, direction, setup_score, fusion_score/grade, evidence, mv/px gates, candles_tail 5, config_version, evidence_hash SHA256 16 deterministic.

## SIG-07 Contract
Signal DB contract per `persistence/models.py::Signal`: signal_id ULID PK, venue, contract_family/contract_type, symbol, market_type, direction, primary_timeframe, created_at, expires_at, state, setup_score, setup_quality, probability, probability_status, expected_r, entry/stop/targets, regime/session, strategy, evidence_hash, analysis_version, config_version. Test `test_signal_persistence_contract_and_docs_eq_code` asserts columns.

## SIG-08 Outcome Tracker
`outcome_tracker.py::compute_net_r(entry,stop,target,costs, direction)` net R = (target-entry-cost)/(entry-stop+cost) LONG, reverse SHORT, taker 5 bps + slippage 2 bps. `label_outcome(mv_pass, px_pass, net_r, would_be_blocked)` → MV_FAIL/PX_BLOCKED/PENDING. `tracker_record` builds SignalOutcome dict for every MV pass including risk-blocked (SIG-08), with net_r Decimal and would_be_blocked_by_risk flag, persisted to `signal_outcomes` table unique signal_id.

*Tests: `tests/unit/test_signals_p06.py` 10 tests covers gates 30+, fusion scoring/grades/hash, illegal transitions extended, TTL expiry, ULID/dedup windows, snapshots deterministic, outcome tracker net R 1.23 and risk-blocked, strategy contract, bi-directional ICT-A, DB contract.*
