# PHASES.md — Implementation Phases (v3.0 Futures-first: P00–P11 = M0 v0.1 + P12–P22 + P99)

> **v3.0 2026-09-20:** P0 now split into P00 Foundations skeleton through P11 Minimal UI encompassing whole-universe futures+Paper; P1–P3 extend to P22 (walk-forward → DOM → Live testnet) + P99 audit. Each capability needs ≥3 free fallbacks (FBK-01) to leave P00. Universe dynamic uncapped (INV-25). Scale ARC-20, futures gates FUT-01..09.


## 11.0 Definition of Done (every phase)
1. Every REQ in phase implemented + at least one test (or TEST_EXEMPT) → traceability updated
2. `python -m gcis.cli verify --full` passed, report at docs/audit/<phase>/verify_report.json else UNVERIFIED_ENV
3. No placeholder in src/ (INV-01/23)
4. Migrations up/down on scratch DB
5. New config keys in config/default.yaml + docs/DEFAULTS.md
6. Docs updated
7. docs/audit/<phase>/REPORT.md per 13.3
8. BUILD_STATE.json + IMPLEMENTATION_PLAN.md updated; commit tagged phase-<id>

Empirical gates (EG) never block a phase → EMPIRICAL_PENDING.

## 11.1 Phase table
| Phase | Tier | Goal | Reqs | DoD additions |
|-------|------|------|------|---------------|
| P00 Foundations | P0 | Skeleton, probe, config, contracts, clock, ids, migrations base, logging, invariant scanner, verify harness | ARC-01..05,08-10,13-16, OPS-05/08, SEC-01/03/06 | env_probe report, verify --quick green, import contracts, lockfile |
| P01 Universe & gateway | P0 | exchangeInfo → registry, rate-limit, time sync, provider status | DAT-01..03,15, ARC-11, OD-01 | Registry from real exchangeInfo or NO DATA |
| P02 Historical | P0 | bulk loader, ms/µs, Parquet, REST tail, quality report | DAT-07,10,14, ARC-07,17 | idempotent, resumable, gap report |
| P03 Live ingest | P0 | WS transport, rotation<24h, gap/backfill, polling fallback, candle integrity, raw recorder, outbox | DAT-04..06,08,09,11, ARC-04/05/13 | Fault-injection handled, 60s live check |
| P04 Market | P0 | Indicators, sessions, regime v1, MarketView(as_of) | ANA-01..04, ARC-06 | Causality, oracle, leakage tests |
| P05 ICT core | P0 | Swings, BOS/CHOCH, displacement, FVG, OB, sweeps, mitigation, breakers, premium | ICT-01..13 | Golden+no-repaint, docs=test |
| P06 Strategy & signals | P0 | ICT-A, gates, fusion, state machines, dedup, expiry, snapshots, Outcome Tracker | STR-01/02, SIG-01..08 | Illegal-transition tests, tracker labels all |
| P07 Risk & Paper | P0 | Risk, daily state, sizing, exposure, kill switch, paper fills, positions, catch-up | RSK-01..09, EXE-01..08 | Atomic kill switch, sizing props, catch-up drill |
| P08 Backtest | P0 | Shared-core backtest, baselines (4), census | BKT-01..06,08,10..12 | Baseline verdict, census tier |
| P09 Runtime | P0 | Supervisor, 4 processes, health, recovery, commands | OPS-01..04,11, ARC-04/05 | Recovery drills, crash-loop breaker |
| P10 Minimal UI — M0 v0.1 | P0 | Read-only terminal, kill switch, banner, health; .bat | UIX-01,03/04,14, ARC-16, OPS-06/07 | UI smoke, verify --post-install (UNVERIFIED_ENV in sandbox) |
| P11 Full terminal | P1 | Full Streamlit: overview, coin detail, charts, Risk Center, Trade Desk | UIX-02,05..13, EXE-02 | Idempotency, forbidden strings |
| P12 Research I | P1 | Walk-forward, Monte Carlo, more strategies | BKT-07,09,13, STR-03/04/05/08 | Purged CV, trial counting |
| P13 Probability A | P1 | Empirical-Bayes, calibration, EV_lcb, ranking | PRB-01..12 Tier A | Gate tests, EV ranking |
| P14 Hardening | P1 | Dynamic correlation, secondary providers, news veto, backup, readiness report | RSK-04, DAT-12/13, OPS-06/09/10, EXE-09 | Discrepancy, retention, readiness |
| ... | P2/P3 | VOL, DOM, CCXT twin, notifications, scalping, live adapter, futures | See spec | ... |

## 13 Acceptance
- Completion vocab: INCOMPLETE → M0 CODE COMPLETE — EMPIRICAL VALIDATION PENDING (max in build) → CODE COMPLETE P0+P1 → PAPER-VALIDATED Ln → PRODUCTION READY (only via Live Readiness Report)
- AC-01..43 mapping in traceability
- Audit report format 13.3; Final audit P99 replay-based per 13.4; Traceability 13.5; End-session message 13.6
