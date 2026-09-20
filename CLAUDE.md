# AGENTS.md — Constitution v3.0 Futures-first (Parts 0 & 1 condensed)

> GLOBALCRYPTOICTSCANNER 2026 — Master Build Prompt v3.0 — Authoring date 2026-09-20 — Futures-first, all contracts, free-only with failover.
> Full spec: `docs/SPEC.md`. Defaults: `docs/DEFAULTS.md` + `config/default.yaml` + `config/sources.yaml`. Phases: `docs/PHASES.md`. Matrix: `DATA_SOURCE_MATRIX.md` (generated from `config/sources.yaml`).

## Part 0 — Execution Protocol

### 0.1 First-session bootstrap (mandatory order)
1. Inspect repo → `docs/REPO_AUDIT.md` (never delete valuable work without inspection).
2. Run `scripts/env_probe.py` → `BUILD_STATE.json → environment` (probes **every venue/provider in failover chains**: Binance UM/CM REST+WS, Bybit, OKX, Hyperliquid, `data.binance.vision`, `public.bybit.com`, keyless secondaries; detects geo 451/403; records `network_venues: {binance_um, bybit, okx, hyperliquid}` + `probed_at`). Never pretend capability.
3. Split document into: AGENTS.md/CLAUDE.md (Part0+1 verbatim short), docs/SPEC.md (2–10, every ID), docs/DEFAULTS.md + config/default.yaml (Part12), docs/PHASES.md (11+13), **Appendix A → `config/sources.yaml` + `DATA_SOURCE_MATRIX.md`** (runtime failover truth, FBK-09), docs/DECISIONS.md (OD-xx, AS-nn), docs/REQUIREMENTS_TRACEABILITY.md, IMPLEMENTATION_PLAN.md, BUILD_STATE.json (schema 0.4).
4. Begin Phase P00 phase-by-phase. Never build UI before engine.

### 0.2 Every session
- **Start:** read AGENTS.md, BUILD_STATE.json, current phase in docs/PHASES.md, only SPEC IDs that phase lists.
- **Work:** implement, test, document. Do not regenerate finished work. Do not start next phase until DoD 11.0 met or phase explicitly `BLOCKED` with reason.
- **End:** run `verify` (OPS-08/TST-01), update BUILD_STATE.json, IMPLEMENTATION_PLAN.md, REQUIREMENTS_TRACEABILITY.md, write `docs/audit/<phase>/REPORT.md` (format 13.3). If context near exhausted, stop at clean boundary.
- **Chat-only:** emit files in dependency order with explicit paths, finish with `RESUME.md` containing current BUILD_STATE.json + next 3 actions.

### 0.3 Ambiguity and conflicts
Do not stop to ask. Use documented default → `AS-nn` in docs/DECISIONS.md. On conflicts obey truth hierarchy 1.1. If requirement cannot be satisfied in current env → `UNVERIFIED_ENV` or `BLOCKED`; never weaken safety. Stop only for true blockers (credential missing for explicitly required step).

### 0.4 BUILD_STATE.json schema (v3)
```json
{
  "implementation_version": "0.0.0",
  "current_phase": "P00",
  "phases": {"P00": "IN_PROGRESS"},
  "environment": {"os": "", "python": "", "postgres": "unknown", "network_venues": {"binance_um": "unknown", "bybit": "unknown", "okx": "unknown", "hyperliquid": "unknown"}, "probed_at": ""},
  "requirements": {"ARC-01": {"status": "NOT_STARTED", "tests": [], "evidence": ""}},
  "operator_decisions": {"OD-01": "default"},
  "assumptions": [],
  "known_failures": [],
  "last_verify": {"command": "", "exit_code": null, "timestamp": "", "log": ""},
  "migration_head": "",
  "current_file_group": "",
  "pending_tasks": [],
  "next_actions": []
}
```

### 0.5 Status vocabulary (exact)
`NOT_STARTED` · `IN_PROGRESS` · `CODE_VERIFIED` · `UNVERIFIED_ENV` · `EMPIRICAL_PENDING` · `EMPIRICALLY_VALIDATED` · `BLOCKED` · `DEFERRED` · `NOT_APPLICABLE`.

### 0.6 Evidence and honesty
CODE_VERIFIED only if named automated test + log under docs/audit/. Never invent results. No placeholders in shipped paths (TODO, pass-only, NotImplemented, hard-coded prices/signals/prob/PnL, mocked runtime). Features not yet built → capability flag + `NOT IMPLEMENTED (tier Pn)` from `docs/FEATURE_STATUS.md`. If network unavailable → mark live requirements UNVERIFIED_ENV + provide `verify --live-checks`; never fabricate recorded payloads. If Windows unavailable → `.bat` UNVERIFIED_ENV (logic lives in Python entrypoints). If PostgreSQL unavailable → first try provision locally; otherwise mark `postgres` tests UNVERIFIED_ENV (SQLite only for unit tests).

### 0.7 Operator decisions defaults (v3)
- **OD-01** Universe: **all** crypto futures contracts listed as tradable on active venue (default: Binance USDⓈ-M perpetuals; other USDⓈ-M/USDC + COIN-M per tier), discovered dynamically from venue registry (DAT-02). No hard-coded list/count (INV-25). Non-crypto (equity/index/commodity) tagged `asset_class`, listed, not analysed by default (`universe.analyze_tradfi=false`, reason `EXCLUDED_ASSET_CLASS`); one flag includes them. Execution eligibility (liquidity/spread/age) is separate from analysis, never silently shrinks analysed set.
- **OD-02** Costs: futures taker 5 bps, maker 2 bps [U], + slippage + funding (FUT-04). Fees never 0.
- **OD-03** Sessions: Part12 conventions (not validated).
- **OD-04** Risk day 00:00 UTC.
- **OD-05** Paper 10,000 USDT.
- **OD-06** DB local PostgreSQL (verify).
- **OD-07** Free public market data only. Default Binance USDⓈ-M. Ordered failover: Binance → Bybit (linear) → OKX (swap) → Hyperliquid → further Appendix A. Geo/unreachable → failover + `VENUE_FALLBACK_ACTIVE`; never circumvent (INV-14). All venues fail → `NO DATA`.
- **OD-08** Live disabled.
- **OD-10** Market profile: FUTURES (linear/USDⓈ-M perp first). Default leverage 3x, ISOLATED, one-way; long+short in Research/Paper (Live shorts via LIVE-01).
- **OD-09** Paper AUTO (EXPERIMENTAL while prob unavailable); Live SEMI_AUTO.

### 0.8 What "deployed" means
Operator runs `install.bat` → `start.bat` on Windows 10/11 → UI with real futures data for whole listed universe (honest coverage banner), healthy workers, migrations at head, Paper running; `healthcheck.bat` healthy; `verify.bat --post-install` green. Completion vocab 13.1: `CODE COMPLETE — EMPIRICAL VALIDATION PENDING` max at build time; `PRODUCTION READY` only via Live Readiness Report after real evidence.

---

## Part 1 — Constitution (highest authority)

### 1.1 Truth hierarchy
Data integrity > market state > ICT/strategy validity > regime compatibility > signal quality > statistical validation > risk > execution > UX > visual effects.

### 1.2 Six honest states
`NO DATA` · `PROBABILITY UNAVAILABLE (N/A+reason)` · `SYSTEM DEGRADED` · `NO TRADE/NO QUALIFIED SETUP` · `NOT VALIDATED` · `NOT IMPLEMENTED`. Prefer NO TRADE over low-quality.

### 1.3 Invariants (machine-enforced where stated)
INV-01 No fabricated data (tests only; scanner allow-list retry jitter/ID/seeded RNG)
INV-02 Freshness (source,timestamps,age,quality; never stale as current)
INV-03 Provider semantics & failover honesty (never average/splice candles; fallback = different series `(venue,contract)`; disagreement recorded)
INV-04 No look-ahead/repaint (only MarketView(as_of); confirmed immutable)
INV-05 Contract-family typing (LINEAR/INVERSE/SPOT distinct; futures fields never on SPOT; every signal carries venue,family,type,symbol)
INV-06 UI never source of truth (no orders/positions/risk/signals/equity in st.session_state; UI reads read-models, writes commands only)
INV-07 Every transition persisted append-only in same DB tx (outbox)
INV-08 Idempotency (unique constraints + idempotency keys)
INV-09 Hard caps (code constants, cannot raise via config): risk/trade ≤0.5%, daily loss ≤2%, ≤10 entries/day; **effective leverage ≤10x; per-position leverage ≤10x; every position must pass liquidation-buffer check (FUT-03)** — raising needs code change + version bump
INV-10 Kill switch/risk/data locks evaluated inside same DB tx as intent/order
INV-11 Probability never invented (only if display gate passes)
INV-12 Reproducibility (config_version, analysis_version, software_version, evidence_hash)
INV-13 Decimal/NUMERIC(38,18), UTC µs
INV-14 Free-only & keyless-complete (no paid APIs; every capability must work with zero keys/paid; no bypass of auth/rate/geo/ToS — failover only)
INV-15 Secrets only in env/OS store
INV-16 Live off by default
INV-17 No destructive startup
INV-18 One decision core (only Clock/DataAdapter/ExecutionAdapter differ)
INV-19 Backtests report fidelity/lineage; degraded → DEGRADED_DATA_TEST
INV-20 No predictive claim without validation vs baselines
INV-21 No business logic / while True in Streamlit
INV-22 Optional adapters may fail without stopping core
INV-23 Docs/UI describe only implemented (FEATURE_STATUS from BUILD_STATE)
INV-25 Universe completeness (no hard-coded lists/top-N/count; analysed = all tradable − reason-coded exclusions; pressure → DEGRADED, never silent skip; every surface shows analysed/listed; scan for literal lists)
INV-26 Source transparency (every datum/signal records venue/source; every switch is append-only source_switch_events + visible UI; fallback never continued without warm-up FBK-05)
INV-27 Futures safety (every sizing models leverage/margin/liquidation/funding; stop must be safely inside liquidation; ISOLATED default)
INV-24 "REAL" = real inputs, deterministic algorithm, persisted state, defined failure mode, automated test, audit trail, documented limitations

`scripts/check_invariants.py` checks INV-01,04,05,06,13,15,21,23,25,26

### 1.4 Two kinds of completion gates
CG code-complete (tests/logs now) vs EG empirical (needs real data/time). EG mechanism is CG; outcome `EMPIRICAL_PENDING` until evidence. EG never blocks build and never reported as passed without evidence.
