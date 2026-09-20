# Audit Report — Phase P12 Research I (P1)

**Header**
- Phase: P12
- Date: 2026-09-20
- Agent: arena session `arena/01a0bfdc-tradeterminal`
- implementation_version: 0.1.13
- git branch: arena/01a0bfdc-tradeterminal
- Verify command: `PYTHONPATH=src python -m gcis.cli verify --full`

**Scope**
Requirement IDs: BKT-07, BKT-09, BKT-13, STR-03/04/05/08 (walk-forward purge/embargo, Monte Carlo block bootstrap, confluence research + extra strategies). Out-of-scope P13-P22/P99. First P1 research after Full terminal.

**What was built**
- `src/gcis/strategies/extra.py` — STR-03/04/05/08 v0.2.0: `evaluate_ema_cross` (EMA9/21 cross causal, entry ±0.15 ATR stop 1.0 ATR tp 2R), `evaluate_donchian` (20-bar Donchian breakout causal, stop opposite channel), `evaluate_rsi_reversion` (RSI14 30/70 + BB 20/2 mean-reversion, entry ±0.2 ATR), `evaluate_confluence` (requires ICT-A + EMA same direction, boosted score min(95, ict+10+ema//5), conf 0.72). All return `StrategyResult` causal, deterministic, Decimal 38/18 style, evidence lists, reason_codes.

- `src/gcis/backtest/walk_forward.py` — BKT-07 purged CV: `walk_forward_splits(df, train_days, test_days, purge_bars, embargo_bars)` computes bars via TF_MIN (1m 1, 5m 5...), generates folds: train | purge | test | embargo, next train starts after embargo, leakage_check test_end<=next_train_start. `run_walk_forward(symbols, timeframe, df_override, train_days, test_days, purge_bars, embargo_bars, strategy_name)` resolves strategy fn via name (ICT-A default else EMA/DONCHIAN/RSI/CONFLUENCE), loops test window bars incrementally with `MarketView(as_of)` causal prefix `df.iloc[:global_i+1]`, creates trades with pessimistic `resolve_exit_pessimistic` stop_first, costs 5bps taker, computes `compute_metrics` per fold + pooled OOS, returns folds_count, fold_results, oos_metrics, leakage_check, lineage.

- `src/gcis/backtest/monte_carlo.py` — BKT-09 block bootstrap: `block_bootstrap_trades(trades, block_size 10, runs 5000, seed 42)` normalizes pnl to float, partitions into blocks size 10, draws blocks with replacement via `Random(42)` to match n, computes boot means 5000 deterministic, ci_95 percentile 2.5/97.5, p_value one-sided vs zero (prop boot<=0 if observed>0), distribution_mean, jitter note. `monte_carlo_from_backtest(backtest_result, ...)` helper reading config `backtest.monte_carlo block_size/runs` and handling capped trades warning. Deterministic seed ensures reproducible.

- `src/gcis/research/__init__.py` + `src/gcis/research/confluence.py` — BKT-13: `analyze_confluence(strategy_results dict)` counts per strat, overlap Jaccard over `entry_bar` sets (inter/union) or direction_agreement fallback, confluence_bars where >=2 dirs same direction, joint_expectancy avg pnl on confluence bars, total_trials, effective_trials_note, survivorship note. `run_confluence_from_engine(symbols, timeframe, df_override, strategies)` patches `gcis.strategies.ict_a.evaluate_ict_a` temporarily to each extra strategy, runs `run_backtest` via engine, then `analyze_confluence`. Purge note preserved.

- `docs/STRATEGY_DEFINITIONS.md` — updated to v0.2.0, added STR-03/04/05/08 sections + P12 Backtest Extensions (BKT-07/09/13 details), source = extra.py + walk_forward/monte_carlo/confluence.

- `tests/unit/test_research_p12.py` — 13 tests: import/version, ema deterministic causal, donchian+rsi contract, confluence boost, walk_forward splits purge/embargo + leakage, walk_forward run OOS, insufficient history, monte carlo deterministic/pvalue/ci, monte from backtest, confluence basic Jaccard + confluence_bars, confluence from engine, no forbidden strings P12, walk_forward no lookahead (future spike not affect first fold).

**Evidence**
- Command: `PYTHONPATH=src python -m pytest tests/unit/test_research_p12.py -v` → **13 passed** 3.0s — all P12 gates deterministic, no repaint, purge respected.
- Command: `PYTHONPATH=src python -m pytest tests/unit -q` → `........................................................................ [56%]` + `........................................................ [100%]` **128 passed** 1 warning 13.6s (115 P11 +13 =128).
- Command: `PYTHONPATH=src python -m gcis.cli verify --full` → 4 checks OK: check_invariants 9/9 (INV-01 06 21 13 15 23 25 26 SEC-09), config_load, db_migrations `sqlite:///var/gcis.db`, pytest 128 dots PASSED ~13s → `verify_report.json` + `docs/audit/P12/verify_report.json` (all_ok true).
- Manual: `walk_forward_splits` purge 24 embargo 12 respected, `block_bootstrap_trades` seed 42 deterministic ci ordering, `analyze_confluence` Jaccard 0.5 for overlap demo.

**Deviations & Decisions**
- Walk-forward bars derived from TF_MIN not calendar (deterministic, avoids timezone drift); train/test days from config `backtest.walk_forward` (180/30/24/12) overridden in tests to small values for speed but logic same.
- Monte Carlo capped at 5000 runs even if config asks higher (performance), deterministic via `random.Random(42)` with jitter allowance comment per INV-01.
- Confluence uses `entry_bar` Jaccard when available (engine now supplies entry_bar), falls back to direction agreement 20-last trades when not — ensures works both with synthetic trades and real engine trades.
- Strategies extra intentionally simple but causal and cost-aware (net RR gate) to avoid fabrication; confluence requires both eligible (strict) to keep joint trials conservative.

**Known limitations / debt**
- Walk-forward currently evaluates test window only, not retraining hyperparams (train not used for optimization yet — pure OOS). Hyperparam search will be P13.
- Monte Carlo currently bootstraps pnl only, not sharpe; block_size fixed not adaptive to autocorrelation estimation.
- Confluence research pooled not yet integrated into supervisor live; will be gated by probability in P13.

**Empirical gates outstanding (EG)**
- Real data 90d bulk needed for meaningful walk-forward folds (>5000 bars) — currently synthetic df tests only, live wall-time 7d not available (TLS blocked).
- Monte Carlo significance needs >100 trades per strategy — synthetic shows INSUFFICIENT path honest.

**Next phase**
P13 Probability A — Empirical-Bayes, calibration, EV_lcb, ranking PRB-01..12 Tier A (gate tests, EV ranking). Update `BUILD_STATE.json current_phase=P13`.

**Status: CODE_VERIFIED (128 tests, 9 invariants, 18 caps) — P12 Research I purged CV + Monte Carlo + 4 strategies + confluence verified — DOCS==CODE**

*Format Part 13.3; evidence at `docs/audit/P12/verify_report.json`. P12 = walk-forward + Monte Carlo + extra strategies.*
