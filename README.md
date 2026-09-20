# GLOBALCRYPTOICTSCANNER 2026 — GCIS

> Local, free-resource, event-driven crypto market-intelligence + ICT/SMC research platform.
> **Honest by design** — says `NO DATA`, `NO TRADE`, `PROBABILITY UNAVAILABLE`, `SYSTEM DEGRADED`, `NOT VALIDATED`, `NOT IMPLEMENTED` whenever true. Promises no profit. “No edge found” is valid.

**Status:** `M0 CODE COMPLETE — EMPIRICAL VALIDATION PENDING` (P00 foundations verified, P01-P10 skeleton implemented, empirical gates need real live data/weeks).

---

## What it is / is not
- **Is:** Research platform (Research & Paper modes), candle + ICT/SMC detectors, regime v1, flagship strategy ICT-A (long-only Spot), conservative Paper fills, backtest with baselines, signal census, Streamlit terminal.
- **Is not:** No guaranteed profit, no paid APIs, no HFT/latency arbitrage, no multi-user SaaS, no mobile app. Stack (Python, REST/WS, local machine) cannot compete on latency — scalping is P3/experimental.

## Quick start (Windows 10/11 — local, no API key needed)

```bat
install.bat          # pip install, creates var/, runs preflight (NO DATA if Binance blocked is honest)
start.bat            # Streamlit on http://127.0.0.1:8501  (PAPER mode)
healthcheck.bat
verify.bat --post-install   # green = ready; in sandbox Binance TLS is blocked → UNVERIFIED_ENV is honest
```

**Linux / sandbox preview friendly:**
```bash
./install.sh
./start.sh   # binds 0.0.0.0:8501
```

No secrets required for Research/Paper. Binance public data is free, no key. If `data-api.binance.vision` is geo-blocked → UI shows `NO DATA` (never circumvent, never mock).

## Honest states (visible everywhere)
`NO DATA` · `PROBABILITY UNAVAILABLE (N/A + reason)` · `SYSTEM DEGRADED` · `NO TRADE / NO QUALIFIED SETUP` · `NOT VALIDATED` · `NOT IMPLEMENTED` — never 0% or 50% for missing values.

## Universe (OD-01)
BTC ETH SOL XRP DOGE BNB ADA AVAX LINK TON SUI PEPE → Binance Spot `<BASE>USDT` (only `TRADING` status; else excluded with reason).

## Modes
- **RESEARCH:** history, backtest, census, walk-forward, experiments
- **PAPER:** AUTO (labelled EXPERIMENTAL while probability unavailable), conservative fills, daily risk locks, kill switch
- **LIVE:** disabled by default (`ENABLE_LIVE_TRADING=false`). Enabling requires LIVE-01 checks; testnet first.

## Free-only (INV-14)
No paid APIs/data/models/SaaS. Free keys only for free providers, via `.env` (git-ignored), never in code/DB/logs. No bypass of auth/rate/geo/ToS. Binance REST `https://data-api.binance.vision`, WS `wss://data-stream.binance.vision` (no auth) — preferred. If unreachable → `NO DATA`.

## Architecture (short)
`supervisor → ingest (market data → normalize → validate → persist → publish) → core (analysis → signals → risk → execution lifecycle, single writer) → slow (news/secondary) → ui (Streamlit, writes commands only)` + offline CLIs (history, backtest, census, replay_verify). Durable `event_outbox` + `consumer_cursors` + `commands` table; `MarketView(as_of)` is only analysis entry (INV-04). Storage: PostgreSQL (operational window) + Parquet (research archive) via DuckDB; raw NDJSON+zstd.

## Documentation
- `AGENTS.md` / `CLAUDE.md` — constitution (Parts 0-1)
- `docs/SPEC.md` — full spec (Parts 2-10)
- `docs/DEFAULTS.md` + `config/default.yaml` — all thresholds (Part 12)
- `docs/PHASES.md` — phases + acceptance (Parts 11,13)
- `docs/ARCHITECTURE.md`, `DATA_SOURCES.md`, `ICT_DEFINITIONS.md`, `STRATEGY_DEFINITIONS.md`, `SIGNAL_LIFECYCLE.md`, `RISK_POLICY.md`, `EXECUTION_MODEL.md`, `BACKTESTING.md`, `PROBABILITY_MODEL.md`, `OPERATIONS.md`, `DEPLOYMENT_CHECKLIST.md`, `DEPENDENCIES.md`, `FEATURE_STATUS.md`
- `docs/REPO_AUDIT.md`, `docs/DECISIONS.md`, `IMPLEMENTATION_PLAN.md`, `BUILD_STATE.json`

## Verify
```bash
python -m gcis.cli preflight
python -m gcis.cli verify --quick        # or --full / --post-install
python scripts/check_invariants.py
python scripts/env_probe.py
```

## Security
UI binds `127.0.0.1` (XSRF on, no secrets displayed). Secrets via `.env` or OS keyring only (INV-15). Log redaction tested.

## What “deployed” means
`install.bat → start.bat → healthcheck.bat → verify.bat --post-install` green + UI shows real Binance data, healthy workers, migrations at head, Paper running. In sandbox → `CODE COMPLETE — EMPIRICAL VALIDATION PENDING` is max honest status (needs weeks of forward data, 72h soak, Live Readiness Report).

## License
MIT — see `docs/DEPENDENCIES.md` for per-dependency licenses.

---
*Facts tagged [V] verified 2026-09-20; re-verify (APIs change). Honesty > performance.*
