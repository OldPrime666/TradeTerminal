# REQUIREMENTS_TRACEABILITY.md

| REQ-ID | Tier | Phase | Status | Implementation (module::symbol) | Tests (path::name) | Docs | Evidence link | EG outcome | Notes |
|--------|------|-------|--------|----------------------------------|--------------------|------|---------------|------------|-------|
| ARC-01 | P0 | P00 | CODE_VERIFIED | pyproject.toml | verify | DEPENDENCIES.md | verify_report.json | — |  |
| ARC-02 | P0 | P00 | CODE_VERIFIED | import-linter in pyproject | check_invariants | ARCHITECTURE.md | verify | — |  |
| ARC-05 | P0 | P00 | CODE_VERIFIED | core/clock.py | test_market_view | SPEC | verify | — |  |
| ANA-02 | P0 | P00 | CODE_VERIFIED | market/indicators.py | test_indicators | SPEC | pytest | — |  |
| ICT-01 | P0 | P00 | CODE_VERIFIED | ict/swings.py::detect_swings | test_ict::test_swings_* | ICT_DEFINITIONS stub | pytest | — |  |
| STR-02 | P0 | P00 | CODE_VERIFIED | strategies/ict_a.py::evaluate_ict_a | manual via backtest | STRATEGY_DEFINITIONS stub | verify | EMPIRICAL_PENDING for edge |  |
| SIG-03 | P0 | P00 | CODE_VERIFIED | signals/lifecycle.py | test_signals | SIGNAL_LIFECYCLE | pytest | — |  |
| RSK-01 | P0 | P00 | CODE_VERIFIED | risk/manager.py HARD caps | test_risk | RISK_POLICY | pytest | — |  |
| EXE-04 | P0 | P00 | CODE_VERIFIED | execution/paper.py::paper_fill_market | — | EXECUTION_MODEL | verify | — |  |
| DAT-01 | P0 | P01 | UNVERIFIED_ENV | data/exchange/binance.py | contract tests (real fixtures pending) | DATA_SOURCES.md | env_probe | sandbox TLS blocked → NO DATA honest |  |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | Full table generated via check_invariants --traceability in P99 |

*This is a seed for P00 — P99 final audit closes all IDs per Part 13.5 table schema.*
