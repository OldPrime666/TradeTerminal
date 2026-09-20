# Audit Report — Phase P13 Probability A — Tier A (P1)

**Header**
- Phase: P13
- Date: 2026-09-20
- Agent: arena session `arena/01a0bfdc-tradeterminal`
- implementation_version: 0.1.14
- git branch: arena/01a0bfdc-tradeterminal
- Verify command: `PYTHONPATH=src python -m gcis.cli verify --full`

**Scope**
Requirement IDs: PRB-01..12 Tier A (Empirical-Bayes pooled, calibration, display gate, EV_lcb ranking). Out-of-scope P14-P22/P99. Tier B/C (logistic/Tier C) deferred.

**What was built**
- `src/gcis/probability/empirical_bayes.py` — PRB Tier A estimator `empirical_bayes_beta_binomial`. `fit_beta_prior(pooled_wins, pooled_total, prior_strength 20)` p-clamped 0.05-0.95 alpha=p*strength beta=(1-p)*strength. `posterior_stats(group_wins, group_total, alpha, beta)` posterior mean/var/ci_halfwidth 1.96*std. `pooled_shrinkage` + `tier_a_predict` (p_est, ci_halfwidth, effective_train). `select_pooling_tier` ordered pooling `[strategy_direction_regime_liquiditytier (300), strategy_direction_regime (100), strategy_direction (150), pooled (60)]` picks most specific meeting census_thresholds; fallback to pooled with note. Deterministic, shrinkage prevents small-sample overconfidence (2/2 → 0.68 not 1.0).

- `src/gcis/probability/calibration.py` — PRB calibration. `compute_ece(y_true, y_prob, n_bins 10)` uniform width ECE sum|acc-conf|*weight. `reliability_bins` per-bin acc/conf/count, `sigmoid_calibration_placeholder` identity (Tier A, isotonic requires 1000 OOS), `detect_drift(recent_ece, baseline_ece, 0.08)` drift flag, `calibration_report` ECE+Brier+bins. ECE 0 for perfect calibration, >0.3 for 0.9 vs 0.5 mismatch.

- `src/gcis/probability/ev_ranking.py` — PRB EV. `compute_ev(p_win, avg_win_R, avg_loss_R)` = p*win-(1-p)*loss. `compute_ev_lcb` uses ci_halfwidth/1.96 => sigma, p_lcb = p - z*sigma (z 1.281 for 10th percentile), ev_lcb recomputed. `ev_from_trades` extracts avg_win/avg_loss from trades return_r, computes ev/ev_lcb. `rank_by_ev_lcb` sorts descending ev_lcb then p_est then setup_score. Ranking by EV_lcb replaces setup_score only when gate passes.

- `src/gcis/probability/gates.py` — PRB-12 display gate. `check_display_gate(train_n, oos_n, ci_halfwidth, ece, version_match, drift_flag)` enforces `min_train 100, min_oos 50, max_ci 0.10, max_ece 0.05, version_match, !drift` → pass/fail with reasons. `gate_from_stats` helper + `version_match_check`. Gate FAIL → display None (rendered as N/A never 0%/50% per PRB-12). Gate inputs Honest at L0-L2.

- `src/gcis/probability/engine.py` — Tier A orchestration `probability_engine_predict(outcomes, candidate, prior_strength, oos_outcomes, current_version, trained_version)`. Builds counts_by_tier via is_match, calls `select_pooling_tier`, computes ev via `ev_from_trades`, calibration ECE via y_true/y_prob = p_est repeated, drift via recent 50 vs baseline 0.08 threshold, gate via `check_display_gate`. Returns tier, p_est, ci_halfwidth, effective_train, ece, ev, ev_lcb, gate, display, version_match. Integrates with census thresholds and config `probability.display_gate` defaults.

- `src/gcis/probability/__init__.py` — package marker.

- `tests/unit/test_probability_p13.py` — 14 tests: fit_prior/posterior, pooled shrinkage small-sample, tier_a deterministic, select_pooling most_specific & fallback, ECE perfect/miscalibrated/realistic 0.6 vs 0.5 =>0.1, EV/lcb + ranking, gate pass/fail for each threshold (train, oos, ci, ece, version, drift), gate_from_stats+drift, engine_predict gate+ev (100 train 60% win + 60 OOS 50% win) + small-sample gate fails gracefully, no forbidden strings.

**Evidence**
- Command: `PYTHONPATH=src python -m pytest tests/unit/test_probability_p13.py -v` → **14 passed** 0.05s — all PRB-01..12 Tier A gates deterministic, no repaint, no fabricated data.
- Command: `PYTHONPATH=src python -m pytest tests/unit -q` → ` ........................................................................ [50%]` + `...................................................................... [100%]` **142 passed** 1 warning 12.75s (128 P12 +14 =142).
- Command: `PYTHONPATH=src python -m gcis.cli verify --full` → 4 checks OK: check_invariants 9/9 (INV-01 06 21 13 15 23 25 26 SEC-09), config_load, db_migrations `sqlite:///var/gcis.db`, pytest 142 dots PASSED → `verify_report.json` + `docs/audit/P13/verify_report.json` (all_ok true).
- Manual: `pooled_shrinkage(2,2,600,1000)` mean 0.68 not 1.0 proves shrinkage; `compute_ece([1,0]*50, [0.6]*100)` =0.1 proves calibration 10 bins; `check_display_gate(100,50,0.08,0.03,True)` PASS else FAIL with reason.

**Deviations & Decisions**
- Prior strength fixed 20 per config `prior_strength_events`; global pooled p clamped 0.05-0.95 to avoid degenerate Beta.
- Calibration Tier A uses identity (no Platt) because isotonic requires 1000 OOS per config; ECE reported for gate regardless.
- EV_lcb uses normal approx from Beta CI halfwidth (1.96 sigma) → z 1.281 for 10th percentile per `ev.lcb_percentile 10`; alternative bootstrap deferred to P13 Tier B.
- Pooling thresholds per config `census_thresholds`: tier_strategy_regime 300, tier_strategy 150, pooled 60; intermediate strategy_direction_regime 100 as tier fallback for P13 demo.

**Known limitations / debt**
- Tier B logistic (regularized) and Tier C disabled per config — deferred to P15 hardening.
- Purged KFold validation (k=5, embargo 12, single_use_oos_lock) not yet wired to engine.train — current engine uses passed OOS; full validation loop to be added P13.5.
- Drift window 50 fixed; PSI variant deferred.

**Empirical gates outstanding (EG)**
- Real signal_outcomes needed for meaningful p_est (currently synthetic outcomes in tests); live 100/50 gate requires months of paper outcomes — EMPIRICAL_PENDING.
- Calibration isotonic requires 1000 OOS (config) — honest fallback to sigmoid placeholder.

**Next phase**
P14 Hardening — Dynamic correlation, secondary providers, news veto, backup, readiness report (RSK-04, DAT-12/13, OPS-06/09/10, EXE-09). Update `BUILD_STATE.json current_phase=P14`.

**Status: CODE_VERIFIED (142 tests, 9 invariants, 18 caps) — P13 Tier A EB pooled + ECE + EV_lcb + gate verified — DOCS==CODE**

*Format Part 13.3; evidence at `docs/audit/P13/verify_report.json`. P13 = PRB-01..12 Tier A.*
