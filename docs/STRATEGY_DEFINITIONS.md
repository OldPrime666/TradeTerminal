# Strategy Definitions — P06 ICT-A

> **Source:** `src/gcis/strategies/base.py` + `src/gcis/strategies/ict_a.py` + `config/default.yaml` strategy block. Version `0.1.0`.

## STR-01 Contract (StrategyResult)
Fields per `strategies/base.py::StrategyResult`:
- `strategy_name` str e.g., "ICT-A"
- `strategy_version` str `0.1.0`
- `eligible` bool
- `direction` LONG/SHORT/None
- `setup_score` int 0-100
- `confidence` float 0-1
- `regime_compatibility` bool
- `entry_zone` tuple(Decimal low, Decimal high) or None
- `invalidation` Decimal stop or None
- `targets` list[Decimal] or None
- `evidence` List[str] explainability
- `reason_codes` List[str] GateReason values
- `required_data` List[str] timeframes
- `data_quality` str HEALTHY/...

Contract is enforced by `docs/STRATEGY_DEFINITIONS.md == code` test.

## STR-02 ICT-A bi-directional
- Config `strategy.ict_a`: enabled true, directions [LONG,SHORT], entry_zone fvg_or_ob_retest, stop_buffer_atr 0.25, tp1_r 1.5 tp2_r 3.0 tp1_close_fraction 0.5, max_holding_bars {5m:96,15m:96}, min_net_rr_tp1 1.2 min_net_rr_final 2.0, version 0.1.0
- HTF `bias_tf 1h`, setup `15m`, trigger `5m` (config analysis_timeframes)
- Flow LONG: HTF BULLISH required (bias from swings+structure) → setup swings/structure → displacement→ bullish sweep (BULL) → FVG/OB bullish → premium→discount (price≤eq) → entry mid-zone, stop = min(zone_low, sweep_low)-0.25 ATR, risk, TP1 1.5R TP2 3R, net R costs 5+2 bps, gates.
- Flow SHORT mirrored: HTF BEARISH, bear sweep, FVG/OB bear, premium (price≥eq), stop = max(zone_high, sweep_high)+0.25 ATR, targets downward.
- Bi-directional evaluation: both directions evaluated, best eligible by setup_score; if none eligible, highest score ineligible returned with reason.
- In-house ICT detectors causal, deterministic, relative ATR/tick thresholds per `docs/ICT_DEFINITIONS.md`.
- Evidence includes HTF bias, swings, displacements, sweeps, FVG/OB counts, entry zone, risk/cost netR.
- `evaluate_ict_a(view, symbol, config)` respects `strategy.ict_a.directions` allowlist; causal (closed candles only as_of), deterministic.

*Test: `tests/unit/test_signals_p06.py::test_strategy_ict_a_long_short_bidirectional_with_view` crafts LONG view (bull bias + bull sweep + FVG) and SHORT view (bear bias + bear sweep) and asserts eligible contract, evidence lists, direction, setup_score.*
