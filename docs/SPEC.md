# docs/SPEC.md — Parts 2–10 (condensed from Master Prompt v3.0 Futures-first 2026-09-20)

> **Master Prompt v3.0 is single source of truth (Parts 0–13 + Appendix A).** Futures-first: every tradable futures contract on active venue, dynamic uncapped (INV-25), free-only ≥3 fallbacks (Appendix A, config/sources.yaml), failover FBK-01..10, no hard-coded list. This file mirrors v2 then amends v3 deltas.

This is the spec mirror for agents: every requirement ID has single line. Full Master Prompt v3.0 is source of truth. This file is kept short for session loading; implementers read Master Prompt Part quoted in AGENTS.md plus this index.

## v3.0 deltas vs v2 (apply on top)
- **Universe (v3 Part 4 DAT-18/19/02):** venue.contract_registry → every futures contract (TRADING) on active venue, fields: venue/symbol/underlying/base_pointer/instrument_type/contract_family/settlement_asset/status/margin_asset/tick/lot. No whitelist caps (INV-25), asset_class tags, coverage_reports DAT-19, GC by contract_lifecycle_rules.
- **Failover (FBK-01..10, Appendix A):** each CAP-01..20 rank PRIMARY + ≥3 free fallbacks (V/U) via config/sources.yaml; controller circuit-breaker/venue warm-up/hysteresis/budget ≤40%; keyless completeness FBK-07; daily reprobe; candidate_pool. Never circumvent geo-block (INV-14/SEC-09 → RESTRICTED).
- **Venues routed:** Binance UM primary (P1 → Bybit→OKX→Hyperliquid→Gate/Bitget chain), WS routed /public /market (≤200 streams/conn, 24h rotation), bulk via data.binance.vision + public.bybit.com.
- **Futures mechanics (FUT-01..09, DAT-12:5, OPS-09:6):** mark/premium/funding per interval, margin tiers/isolation+hedge modes, liquidation on mark+buffer 0.5×liq-distance+1 ATR (FUT-03), inverse PnL, contract lifecycle/expiry/funding timer, effective leverage, market-beta cluster.
- **Scale (ARC-20):** 1m base parquets only (HTF derived, checked), sharded WS by streams/conn, incremental engine (only affected contracts), prioritised scheduling (landing-scanner-level2+derivatives, in-risk-set), bundle budget 20s → ANALYSIS_LAG (never silent skip); NOT_SUBSCRIBED status.
- **Tiers:** P0 skeleton now P00–P11 = M0 v0.1 whole-universe futures+Paper (was P0–P10); P1–P3 up to P22 + P99 audit. LEV HARD 3 default / 10 HARD_MAX (FUT-02).


## Part 2 Scope/tiers
- P0 skeleton v0.1: real data (history+live) → candles/indicators/sessions → MarketView → ICT detectors → regime v1 → ICT-A → gates/fusion/lifecycle → risk → Paper → outcomes → backtest+baselines+census → supervisor/health → minimal read-only UI + kill switch → .bat+verify
- P1 core platform, P2 depth, P3 optional — see Master Prompt
- Ladder L0 data/structure (CG) → L1 forward collection (counterfactual, Paper AUTO experimental, probability N/A, TOP UNVALIDATED) → L2 validated → L3 probability → L4 paper-mature

## Part 3 Architecture
ARC-01 deps pinned, ARC-02 layering, ARC-03 single-writer, ARC-04 outbox+NOTIFY, ARC-05 deterministic Clock, ARC-06 MarketView(as_of), ARC-07 PG+Parquet, ARC-08 config versioning, ARC-09 evidence_hash, ARC-10 backpressure, ARC-11 gateway, ARC-12 Spot≠Futures, ARC-13 Decimal/µs UTC, ARC-14 JSON logs+metrics, ARC-15 tree, ARC-16 Windows.bat thins, ARC-17 checkpointed jobs, ARC-18 caching, ARC-19 schema+domain objects

## Part 4 Data
DAT-01 matrix (binance V, coinpaprika V, etc. — see DAT-01 in prompt), DAT-02 universe registry from exchangeInfo, DAT-03 adapters (native Binance hot path, CCXT twin P2), DAT-04 WS ≥2 conns with rotation<24h+gap detection, DAT-05 state machine, DAT-06 polling fallback, DAT-07 candle integrity (Decimal, idempotent), DAT-08 freshness/quality, DAT-09 raw recorder NDJSON+zstd, DAT-10 bulk loader data.binance.vision with ms/µs normalize, DAT-11 QuoteBar 250ms, DAT-12 secondary (metadata only, never overwrite), DAT-13 news veto/blackout, DAT-14 quality report, DAT-15 provider_status, DAT-16 trade archive, DAT-17 depth recorder

## Part 5 Analysis
ANA-01 timeframes 1m..1d hierarchy, ANA-02 feature engine in-house, ANA-03 sessions tz aware, ANA-04 regime v1 (ADx/ER/BB/ATR percentiles, 3 tags + agreement)
ICT-01 swings (L=R=3), ICT-02 structure BOS/CHOCH, ICT-03 displacement, ICT-04 FVG, ICT-05 OB, ICT-06 sweeps, ICT-07 mitigation, ICT-08 breaker, ICT-09 premium/discount OTE 0.62-0.79, ICT-10 HTF/LTF policy NO_TRADE, ICT-11 relative units, ICT-12 golden+no-repaint, ICT-13 docs==code
STR-01 contract, STR-02 ICT-A long-only Spot (sweep→displacement→BOS→FVG/OB retest discount), STR-03..07 deferred
PSY-01 proxies, VOL-01 volume profile from aggTrades, DOM-01 orderbook engine P3

## Part 6 Signals & Probability
SIG-01 gates MV/PX with 30+ reason codes, SIG-02 fusion setup_score 0-100, SIG-03 state machines (signal/order/position), SIG-04 identity+dedupe ULID, SIG-05 TTL, SIG-06 snapshots+explainability, SIG-07 contract, SIG-08 Outcome Tracker (every MV-pass gets net R, also risk-blocked)
PRB-01..12 pooled empirical-Bayes, calibration, display gate (100 train,50 OOS, CI10%, ECE5%, version, drift), EV_lcb ranking, at L0-L2 TOP UNVALIDATED by score

## Part 7 Risk & Execution
RSK-01 hard caps (0.5/2%/10 via code), RSK-02 daily state 00:00 UTC incl unrealised, RSK-03 sizing round down, RSK-04 correlation static+dynamic, RSK-05 cooldowns, RSK-06 kill switch (separate close), RSK-07 contracts, RSK-08 drawdown, RSK-09 evidence log
EXE-01 policies AUTO/SEMI_AUTO, EXE-02 commands+ENTER TRADE 17 checks atomically, EXE-03 paper account 10k, EXE-04 conservative fills (no mid, trade-through, ambiguous flag), EXE-05 position mgmt, EXE-06 downtime catch-up, EXE-07 outcomes MAE/MFE, EXE-08 contract, EXE-09 readiness report
LIVE-01..10 off by default, testnet, exchange-resident stops, idempotency, reconciliation

## Part 8 Backtest
BKT-01 same core, BKT-02 fidelity levels + pessimistic intrabar, BKT-03 realism, BKT-04 lineage, BKT-05 4 baselines + verdict, BKT-06 census Tier verdict, BKT-07 walk-forward purge/embargo, BKT-08 metrics 365d, BKT-09 Monte Carlo, BKT-10 backtestability statuses, BKT-11 paper-vs-backtest consistency, BKT-12 survivorship, BKT-13 confluence research

## Part 9 UI
UIX-01 minimal read-only, UIX-02 multipage fragment 2s/5s, UIX-03 lineage truthfulness (never 0/50), UIX-04 banner, UIX-05 overview (STRONGEST by EV_lcb else NONE+TOP UNVALIDATED, scanner never fabricated prob, news ticker), UIX-06 coin detail (regime/ICT/orderbook freshness), UIX-07 charts Plotly from engine state + as-of toggle capped 800, UIX-08 Risk Center/Trade Desk via commands, UIX-09 performance/research, UIX-10 health/readiness, UIX-11 sidebar, UIX-12 theme dark navy, UIX-13 error UX, UIX-14 security 127.0.0.1 XSRF

## Part 10 Ops/Sec/Test/Docs
OPS-01 supervisor backoff 1s→60s jitter crash-loop >5/10m FAILED, OPS-02 heartbeats ≤5s, OPS-03 preflight, OPS-04 recovery idempotency, OPS-05 JSON logs redacted, OPS-06 retention+backup, OPS-07 guarded resets, OPS-08 verify harness, OPS-09 metrics 1m rollups, OPS-10 alerts, OPS-11 runbook
SEC-01 secrets .env only, SEC-02 bind loopback, SEC-03 validation, SEC-04 optional auth, SEC-05 SSRF-safe fetcher, SEC-06 pip-audit, SEC-07 audit trail, SEC-08 live creds
TST-01 pyramid 10 types, TST-02 fixtures synthetic vs real, TST-03 coverage ≥90 core, TST-04 fingerprint, TST-05 oracle, TST-06 recovery drills, TST-07 budgets, TST-08 honest reporting
DOC-01 files per code, DOC-02 neutral language, DOC-03 in-app help
