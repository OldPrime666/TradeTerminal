# REQUIREMENTS_TRACEABILITY.md

| REQ-ID | Tier | Phase | Status | Implementation (module::symbol) | Tests (path::name) | Docs | Evidence link | EG outcome | Notes |
|--------|------|-------|--------|----------------------------------|--------------------|------|---------------|------------|-------|
| ARC-01 | P0 | P00 | CODE_VERIFIED | pyproject.toml | verify | DEPENDENCIES.md | verify_report.json | — |  |
| ARC-02 | P0 | P00 | CODE_VERIFIED | import-linter in pyproject | check_invariants | ARCHITECTURE.md | verify | — |  |
| ARC-05 | P0 | P00 | CODE_VERIFIED | core/clock.py | test_market_view | SPEC | verify | — |  |
| ARC-11 | P0 | P01 | CODE_VERIFIED | data/gateway.py::ProviderGateway (TokenBucket 50% budget, retry 3x jitter, status counters) | test_universe::test_gateway via sync_registry | SPEC ARC-11 | verify --full | — | rate-limit ≤50% + circuit breaker |
| ANA-02 | P0 | P00 | CODE_VERIFIED | market/indicators.py | test_indicators | SPEC | pytest | — |  |
| ICT-01 | P0 | P00 | CODE_VERIFIED | ict/swings.py::detect_swings | test_ict::test_swings_* | ICT_DEFINITIONS stub | pytest | — |  |
| STR-02 | P0 | P00 | CODE_VERIFIED | strategies/ict_a.py::evaluate_ict_a | manual via backtest | STRATEGY_DEFINITIONS stub | verify | EMPIRICAL_PENDING for edge |  |
| SIG-03 | P0 | P00 | CODE_VERIFIED | signals/lifecycle.py | test_signals | SIGNAL_LIFECYCLE | pytest | — |  |
| RSK-01 | P0 | P00 | CODE_VERIFIED | risk/manager.py HARD caps | test_risk | RISK_POLICY | pytest | — |  |
| EXE-04 | P0 | P00 | CODE_VERIFIED | execution/paper.py::paper_fill_market | — | EXECUTION_MODEL | verify | — |  |
| DAT-01 | P0 | P01 | CODE_VERIFIED | config/sources.yaml (Appendix A truth) + config/default.yaml universe.venue_chain | test_universe + source_matrix_check | DATA_SOURCE_MATRIX.md | source_matrix_check 18/18 PASSED + DATA_SOURCE_MATRIX.md | — | ≥3 free fallbacks, keyless-complete FBK-07 V/U |
| DAT-02 | P0 | P01 | CODE_VERIFIED | data/universe.py::sync_registry + data/exchange/binance_um.py::parse_exchange_info etc. | test_universe::test_binance_um_parse + test_registry_sync_using_fixture + test_registry_idempotent + fixtures/real/* | SPEC DAT-02 | docs/audit/P01/verify_report.json + var/gcis.db 5 contracts | EMPIRICAL_PENDING for live wall-time 7d 0 gaps | dynamic discovery INV-25, no hard-coded list, CONTRACT_TRADING 5, fixtures prove offline CODE_VERIFIED; live TLS blocked → NO DATA honest + fixture fallback |
| DAT-03 | P0 | P01 | CODE_VERIFIED | data/exchange/base.py + binance_um.py + binance_cm.py + bybit.py + okx.py + hyperliquid.py (native httpx, no key, free) | test_universe::test_*_parse (4 venues) | SPEC DAT-03 | verify --full | CCXT twin deferred P2 |
| DAT-15 | P0 | P01 | CODE_VERIFIED | persistence/models.py::ProviderStatus + VenueStatus + universe.py status updates (HEALTHY/RESTRICTED/DISCONNECTED, latency, circuit_state) | test_universe::test_registry_sync_using_fixture (checks ProviderStatus) | SPEC | sync-registry output + var/gcis.db | — | per-capability status, SourceSwitchEvent on failover |
| INV-25 | P0 | P01 | CODE_VERIFIED | universe.py no hard-coded list + streamlit_app.py dynamic ContractRegistry + check_invariants scan | test_universe::test_no_hardcoded_universe + check_invariants | AGENTS.md INV-25 | check_invariants 9/9 OK | — | |
| INV-26 | P0 | P01 | CODE_VERIFIED | persistence/models::SourceSwitchEvent + VenueStatus + universe.py + streamlit banners | test_universe::test_registry_sync_using_fixture | SPEC | check_invariants 9/9 OK | — | |
| SEC-09 | P0 | P01 | CODE_VERIFIED | base.py::_detect_geo_block (451/403) + universe.py failover without circumvention + check_invariants SEC-09 | test_registry_sync_using_fixture (451) | SPEC | verify | — | never vpn/proxy |
| CAP-01_registry | P0 | P01 | CODE_VERIFIED | universe.py chain binance_um→bybit→okx→hyperliquid + sources.yaml CAP-01 | test_universe fixtures + source_matrix_check | DATA_SOURCE_MATRIX.md | source_matrix_check PASSED | — | 451/429/5xx/timeout warm-up 500 FBK-05 |
| CAP-14_time_sync | P0 | P01 | CODE_VERIFIED | data/time_sync.py (venue → NTP → HTTP Date) | manual via preflight | SPEC | preflight log | UNVERIFIED_ENV NTP pool in sandbox (NTP blocked) | |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | Full table generated via check_invariants --traceability in P99 |

*This is a seed for P00 — P99 final audit closes all IDs per Part 13.5 table schema.*
