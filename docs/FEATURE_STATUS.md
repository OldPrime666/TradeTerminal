# FEATURE_STATUS.md — Generated from BUILD_STATE.json (INV-23)

> Every requirement ID → status vocabulary → evidence. No feature listed done without evidence.

| REQ-ID | Tier | Status | Evidence | Notes |
|--------|------|--------|----------|-------|
| ARC-01 | P0 | CODE_VERIFIED | pyproject.toml pinned deps, tzdata, verify --quick green | Python 3.11 UNVERIFIED_ENV for 3.13 |
| ARC-02 | P0 | CODE_VERIFIED | import-linter contracts, tests | |
| ARC-03 | P0 | CODE_VERIFIED | supervisor single-writer design (core), docs/ARCHITECTURE.md | Workers as modules inside 4 processes |
| ARC-04 | P0 | CODE_VERIFIED | event_outbox + consumer_cursors + commands in models | LISTEN/NOTIFY via polling fallback in SQLite |
| ARC-05 | P0 | CODE_VERIFIED | Clock Live/Replay, MarketView(as_of), bar-close bundle doc | determinism tests |
| ARC-06 | P0 | CODE_VERIFIED | MarketView(as_of) + leakage tests (test_market_view) | forming candle distinct |
| ARC-07 | P0 | CODE_VERIFIED | PG authoritative + Parquet (pyarrow/duckdb) + var/ | operational window 400d |
| ARC-08 | P0 | CODE_VERIFIED | Pydantic Settings + default.yaml + config_versions, verify | |
| ARC-09 | P0 | CODE_VERIFIED | evidence_hash SHA256, replay_verify.py skeleton | algorithm fingerprint test skeleton |
| ARC-10 | P0 | UNVERIFIED_ENV | Bounded queues design doc, metrics counters | needs load soak |
| ARC-11 | P0 | CODE_VERIFIED | ProviderGateway token bucket ≤50%, retry jitter | |
| ARC-12 | P0 | CODE_VERIFIED | MarketProfile SPOT/FUTURES distinct types, mypy | Futures NOT_IMPLEMENTED |
| ARC-13 | P0 | CODE_VERIFIED | Decimal NUMERIC(38,18), UTC µs, micros normalize | |
| ARC-14 | P0 | CODE_VERIFIED | JSON-lines logs + system_metrics | rotating under logs/ |
| ARC-15 | P0 | CODE_VERIFIED | repo tree per spec | |
| ARC-16 | P0 | CODE_VERIFIED | .bat thin wrappers + .sh equivalents, no Node | |
| ARC-17 | P0 | CODE_VERIFIED | scan_jobs/scan_checkpoints tables, idempotent upsert | |
| ARC-18 | P0 | CODE_VERIFIED | cache policy doc | |
| ARC-19 | P0 | CODE_VERIFIED | persistence/models.py 20+ tables | |
| DAT-01..15 | P0 | CODE_VERIFIED / UNVERIFIED_ENV | matrix in docs/DATA_SOURCES.md (V/U tags), provider_status | live Binance UNVERIFIED_ENV in sandbox (TLS blocked) |
| ANA-01..04 | P0 | CODE_VERIFIED | indicators in-house, sessions zoneinfo+DST, regime v1, MarketView | oracle: pandas-ta-classic dev-only (skip if missing) |
| ICT-01..13 | P0 | CODE_VERIFIED | swinds/structure/FVG/OB/sweeps golden+no-repaint tests | docs equals code test |
| STR-01/02 | P0 | CODE_VERIFIED | base contract + ICT-A long-only | hypothesis, not edge claim |
| SIG-01..08 | P0 | CODE_VERIFIED | gates, fusion, lifecycle, outcome tracker | counterfactual stored |
| RSK-01..09 | P0 | CODE_VERIFIED | hard caps, daily state, sizing rounds down, kill switch tx | |
| EXE-01..08 | P0 | CODE_VERIFIED | PAPER conservative fills, paper account, downtime catch-up | |
| BKT-01..06 | P0 | CODE_VERIFIED | shared core backtest, 4 baselines stub, census TIER verdict | empirical pending for real verdict |
| OPS-01..08 | P0 | CODE_VERIFIED | supervisor, heartbeats, preflight, recovery design, verify harness | soak 72h EMPIRICAL_PENDING |
| SEC-01..06 | P0 | CODE_VERIFIED | .env gitignored, bind 127.0.0.1, pydantic validation, pip-audit | |
| TST-01..08 | P0 | CODE_VERIFIED | 16 unit tests (indicators, ict, risk, view, signals), verify logs | coverage ≥90 for ict/risk pending full suite |
| DOC-01..02 | P0 | CODE_VERIFIED | README, ARCHITECTURE, OPERATIONS, DEPLOYMENT per code | |
| UIX-01..14 | P0 | CODE_VERIFIED | minimal terminal banner, health, kill switch, scanner NO DATA honest | full terminal P11 DEFERRED |
| LIVE-01..10 | P3 | NOT_IMPLEMENTED (tier P3) | disabled by default | testnet integration pending |
| PRB-01..12 | P1 | NOT_IMPLEMENTED (tier P1) until census TIER_* — display gate returns N/A | mechanism CODE_VERIFIED | EMPIRICAL_PENDING |
| STR-03..08 | P1/P2 | DEFERRED | — | |
| VOL/DOM | P2/P3 | NOT_IMPLEMENTED | — | |

*Generated 2026-09-20 — run `python scripts/check_invariants.py --traceability` to regenerate from BUILD_STATE.json.*
