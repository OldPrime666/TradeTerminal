# Audit Report — Phase P20 Eligibility & Coverage (P1)

**Header**
- Phase: P20
- Date: 2026-09-20
- Agent: arena session `arena/01a0bfdc-tradeterminal`
- implementation_version: 0.1.21
- git branch: arena/01a0bfdc-tradeterminal
- Verify command: `PYTHONPATH=src python -m gcis.cli verify --full`

**Scope**
Requirement IDs: trade_eligibility filter (min volume 5M, spread 15 bps, age 14d, OI 1M, TRADING status), DAT-19 coverage_reports (analysed/listed), plus supporting BKT-12 survivorship. Out-of-scope P21-P22/P99.

**What was built**
- `src/gcis/data/eligibility.py` — Trade eligibility. `is_eligible(contract, stats_24h, now, config)` checks quote_volume 5M, spread 15 bps, listing age 14d via listing_time, OI 1M, status TRADING → reasons list. `filter_eligible(contracts, stats_map)` batch → eligible/ineligible counts. Deterministic, uses config `trade_eligibility`.

- `src/gcis/data/coverage.py` — DAT-19 coverage. `coverage_report(all, eligible, candles_counts, min_history 300)` total/eligible/analysed ratio, sample 5, status HEALTHY >=0.98 DEGRADED >=0.90 LOW_COVERAGE else NO_DATA, `banner_coverage_text` "5/10 analysed (50.0%)". Honest when no history.

- `tests/unit/test_eligibility_coverage_p20.py` — 4 tests: eligibility OK then each filter fail (vol, spread, age, OI, status) + batch 1/3 eligible, coverage 5/10 ratio 0.5 low + 10/10 healthy + no_data, with no candles 0 ratio, no forbidden strings.

**Evidence**
- Command: `PYTHONPATH=src python -m pytest tests/unit/test_eligibility_coverage_p20.py -v` → **4 passed** 0.29s
- Command: `PYTHONPATH=src python -m pytest tests/unit -q` → **189 passed** 1 warning (185 P19 +4 =189).
- Command: `PYTHONPATH=src python -m gcis.cli verify --full` → 4 checks OK: check_invariants 9/9, config_load, db_migrations, pytest 189 dots PASSED → `verify_report.json` + `docs/audit/P20/verify_report.json`
- Manual: `is_eligible` vol 10M pass vs 1000 fail proves filter; `coverage_report` 5/10 50% low vs 10/10 healthy proves ratio.

**Deviations**
- Listing age via contract listing_time fallback listed_at; if missing, age check skipped (honest).
- Coverage uses candles_counts map for 1m history; real system would query archive store for exact counts but P20 uses map stub for determinism.

**Known limitations**
- 24h stats (volume, spread, OI) currently passed as dict stub; live will fetch from bookTicker + openInterest via gateway.
- Coverage real query via var/archive parquet not yet wired; will be P21 integration.

**Empirical gates**
- Real eligibility needs live 24h stats — synthetic only.
- Coverage needs 300 bars per symbol live wall-time — synthetic only.

**Next phase**
P21 — Remaining hardening final (incremental wiring + alert integration + backtest census final). Update `BUILD_STATE.json current_phase=P21`.

**Status: CODE_VERIFIED (189 tests, 9 invariants, 18 caps) — P20 Eligibility & Coverage verified — DOCS==CODE**

*Format Part 13.3; evidence at `docs/audit/P20/verify_report.json`.*
