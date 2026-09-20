# Strategy Definitions — P06 ICT-A + P12 Extras (STR-03/04/05/08)

> **Source:** `src/gcis/strategies/base.py` + `src/gcis/strategies/ict_a.py` + `src/gcis/strategies/extra.py` + `config/default.yaml` strategy block. Version `0.2.0` (P12).

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

## STR-03 EMA-CROSS (P12)
- Config `strategy.ema_cross`: fast 9 slow 21 stop_atr 1.0 tp_r 2.0 min_net_rr 1.0 version 0.2.0
- Flow: 15m setup timeframe, ema fast/slow causal (pandas ewm), cross detection prev≤prev & cur>cur => LONG, opposite => SHORT, entry zone cur_close ±0.15 ATR, stop cur±stop_atr*ATR, tp risk*tp_r, netR costs 5+2 bps, gates via quality.
- Deterministic, no-repaint (prev vs cur only), eligible only on cross bar.

## STR-04 DONCHIAN Breakout (P12)
- Config `strategy.donchian`: lookback 20 stop_atr 1.0 tp_r 2.5 min_net_rr 1.2
- Flow: Donchian channel high/low of prior 20 bars (excluding current), close > channel high => LONG breakout, close < channel low => SHORT, entry close±0.1 ATR, stop opposite channel ±0.2 ATR or stop_atr fallback, tp risk*tp_r.
- Causal (prior window excludes current), deterministic.

## STR-05 RSI Reversion (P12)
- Config `strategy.rsi_reversion`: rsi_period 14 oversold 30 overbought 70 stop_atr 1.2 tp_r 1.8
- Flow: RSI Wilder 14 + Bollinger 20/2, oversold LONG requires RSI<30 and close within 5% of lower BB, overbought SHORT requires RSI>70 and close near upper BB, entry close±0.2 ATR, stop atr*stop_atr, tp 1.8R.
- Mean-reversion, causal.

## STR-08 CONFLUENCE (P12, BKT-13)
- Config reuse ict_a + ema_cross, version 0.2.0
- Flow: requires ICT-A eligible AND EMA-CROSS eligible same direction; if mismatch or either ineligible => ineligible with reason; if both agree => boosted score min(95, ict_score+10+ema_score//5), confidence 0.72, uses ICT entry/stop/target but combined evidence.
- Joint research via `src/gcis/research/confluence.py` overlap Jaccard + joint expectancy.

*Tests: `tests/unit/test_research_p12.py` covers STR-03/04/05/08 contract, determinism, walk-forward, Monte Carlo, confluence.*

## P12 Backtest Extensions
- **BKT-07 Walk-forward** `src/gcis/backtest/walk_forward.py`: walk_forward_splits/train_days+test_days+purge/embargo, leakage_check test_end <= next train_start, run_walk_forward OOS pooled via MarketView+strategy fn.
- **BKT-09 Monte Carlo** `src/gcis/backtest/monte_carlo.py`: block_bootstrap_trades block_size 10 runs 5000 seed 42 deterministic, ci_95 percentile, p_value one-sided vs zero.
- **BKT-13 Confluence** `src/gcis/research/confluence.py`: analyze_confluence counts/overlap Jaccard/joint_expectancy, effective_trials_note, survivorship-aware.
