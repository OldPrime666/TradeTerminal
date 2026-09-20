# IMPLEMENTATION_PLAN.md — Phase checklist

## P00 Foundations — IN_PROGRESS
- [x] Inspect repo → docs/REPO_AUDIT.md
- [x] Run scripts/env_probe.py → BUILD_STATE.json
- [x] Create AGENTS.md / CLAUDE.md (Part0+1)
- [x] Create config/default.yaml (Part12) + docs/*
- [x] Create pyproject.toml + requirements.in + .env.example
- [x] Create src/gcis core: enums, clock, ids, config, versioning
- [x] Create persistence models + db (SQLite fallback)
- [x] Create market: candles, indicators, sessions, regime, view
- [x] Create ICT detectors: swings, structure, displacement, FVG, OB, sweeps
- [x] Create strategy ICT-A, signals gates/fusion/lifecycle, risk manager, paper fills
- [x] Create data: binance adapter, gateway
- [x] Create runtime health + app streamlit_app
- [x] Create cli + verify harness + invariant scanner
- [ ] Install deps, run preflight, run verify --quick, fix failures
- [ ] Write docs/audit/P00/REPORT.md
- [ ] Tag phase-P00, advance BUILD_STATE to P01

## P01 Universe & gateway — NOT_STARTED
- [ ] exchangeInfo → universe_registry persisted, contract tests with recorded payloads
- [ ] ProviderStatus per provider

## P02 Historical — NOT_STARTED
- [ ] Bulk loader data.binance.vision zip handling, ms/µs normalize, Parquet
- [ ] DAT-14 quality report

## P03 Live ingest — NOT_STARTED
- [ ] WS transport 2 conns, rotation <24h, gap detection, polling fallback, recorder

## ... (P04-P99 per PHASES.md)
