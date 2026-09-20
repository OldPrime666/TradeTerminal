# AGENTS.md — Constitution (Parts 0 & 1 verbatim condensed)

> GLOBALCRYPTOICTSCANNER 2026 — Master Build Prompt v2.0 — Authoring date 2026-09-20
> This file = Part 0 + Part 1 verbatim (short). Full spec: `docs/SPEC.md`. Defaults: `docs/DEFAULTS.md` + `config/default.yaml`. Phases: `docs/PHASES.md`.

## Part 0 — Execution Protocol

### 0.1 First-session bootstrap (mandatory order)
1. Inspect repo → `docs/REPO_AUDIT.md`.
2. Run `scripts/env_probe.py` → `BUILD_STATE.json → environment`. Never pretend capability.
3. Split spec into AGENTS.md/CLAUDE.md (Part 0+1), docs/SPEC.md (Parts 2–10), docs/DEFAULTS.md + config/default.yaml (Part12), docs/PHASES.md (11+13), docs/DECISIONS.md (OD-xx, AS-nn), docs/REQUIREMENTS_TRACEABILITY.md, IMPLEMENTATION_PLAN.md, BUILD_STATE.json.
4. Begin Phase P00 strictly phase by phase. Never build UI before engine.

### 0.2 Every session
Start: read AGENTS.md, BUILD_STATE.json, current phase in docs/PHASES.md, only SPEC sections for that phase.
Work: implement, test, document. Do not regenerate finished work.
End: run `verify` (OPS-08/TST-01), update BUILD_STATE.json, IMPLEMENTATION_PLAN.md, REQUIREMENTS_TRACEABILITY.md, write `docs/audit/<phase>/REPORT.md` (format 13.3).

### 0.3 Ambiguity
Do not stop to ask. Use documented default → AS-nn in docs/DECISIONS.md. Obey truth hierarchy 1.1 on conflicts. Mark UNVERIFIED_ENV/BLOCKED never weaken safety.

### 0.4 BUILD_STATE.json schema
See master prompt §0.4 — fields: implementation_version, current_phase, phases, environment{os,python,postgres,network_binance,probed_at}, requirements{REQ→status/tests/evidence}, operator_decisions, assumptions, known_failures, last_verify, migration_head, current_file_group, pending_tasks, next_actions.

### 0.5 Status vocabulary (exact)
`NOT_STARTED` `IN_PROGRESS` `CODE_VERIFIED` `UNVERIFIED_ENV` `EMPIRICAL_PENDING` `EMPIRICALLY_VALIDATED` `BLOCKED` `DEFERRED` `NOT_APPLICABLE`.

### 0.6 Evidence & honesty
CODE_VERIFIED only if named automated test passed + log saved under docs/audit/. Never invent results. No placeholders in shipped paths (TODO, pass-only, NotImplemented, hard-coded prices/signals/probabilities/PnL). Features not built → capability flag + `NOT IMPLEMENTED (tier Pn)` from docs/FEATURE_STATUS.md.

### 0.7 Operator decisions defaults
OD-01 Universe BTC ETH SOL XRP DOGE BNB ADA AVAX LINK TON SUI PEPE → Binance Spot <BASE>USDT
OD-02 Fees 10 bps/side
OD-03 Session windows Part12
OD-04 Risk day 00:00 UTC
OD-05 Paper 10,000 USDT
OD-06 DB local PostgreSQL (verify)
OD-07 Exchange: Binance public market data; if unreachable → NO DATA; never circumvent
OD-08 Live disabled
OD-09 Paper AUTO (EXPERIMENTAL while prob unavailable); Live SEMI_AUTO

### 0.8 What "deployed" means
Operator runs install.bat → start.bat on Win10/11 → UI with real Binance data, healthy workers, migrations at head, Paper running; healthcheck.bat healthy; verify.bat --post-install green. Deliver docs/DEPLOYMENT_CHECKLIST.md + verify --post-install.

---

## Part 1 — Constitution (highest authority)

### 1.1 Truth hierarchy
Data integrity > market state > ICT/strategy validity > regime compatibility > signal quality > statistical validation > risk > execution > UX > visual effects.

### 1.2 Six honest states (visible in UI/API)
`NO DATA` · `PROBABILITY UNAVAILABLE (N/A + reason)` · `SYSTEM DEGRADED` · `NO TRADE / NO QUALIFIED SETUP` · `NOT VALIDATED` · `NOT IMPLEMENTED`. Prefer NO TRADE over low-quality trade.

### 1.3 Invariants (machine-enforced where stated)
INV-01 No fabricated data (tests synthetic only; runtime must not import tests; scanner checks random/faker)
INV-02 Freshness — every datum carries source,timestamps,age,quality; stale never shown as current
INV-03 Provider semantics — never swap/average prices; secondary never overwrites canonical
INV-04 No look-ahead/repaint — analysis only via MarketView(as_of); confirmed structure immutable; forming candles distinct type
INV-05 Spot≠Futures — distinct types/pipelines
INV-06 UI never source of truth — no orders/positions/risk in Streamlit session state; UI reads read-models, writes commands only
INV-07 Every state transition persisted as append-only event in same DB transaction (outbox)
INV-08 Idempotency — dedupe keys, unique constraints
INV-09 Hard risk caps (code constants, config cannot raise): risk/trade ≤0.5% equity, daily loss ≤2%, ≤10 entries/day
INV-10 Kill switch/risk/data locks evaluated inside same DB transaction as intent/order
INV-11 Probability never invented — only if display gate passes; heuristic scores never called probability
INV-12 Reproducibility — every signal/backtest references config_version, analysis_version, software_version, evidence_hash
INV-13 Numerics/time — Decimal/NUMERIC(38,18), floats only for features, UTC timestamptz µs, no naive datetimes
INV-14 Free-only — no paid APIs; no bypass of auth/rate/geo/ToS
INV-15 Secrets only in env/OS store — never code/DB/logs/Git; log redaction tested
INV-16 Live off default ENABLE_LIVE_TRADING=false
INV-17 No destructive startup
INV-18 One decision core shared across Research/Paper/Live; only Clock/DataAdapter/ExecutionAdapter differ
INV-19 Backtests report data fidelity/lineage; degraded → DEGRADED_DATA_TEST
INV-20 No claim of predictive power without validation vs baselines
INV-21 No business logic / while True loops in Streamlit
INV-22 Optional adapters may fail without stopping core
INV-23 Docs/UI describe only implemented behaviour (FEATURE_STATUS from BUILD_STATE)
INV-24 "REAL" = real inputs, deterministic algorithm, persisted state, defined failure mode, automated test, audit trail, documented limitations

`scripts/check_invariants.py` checks INV-01,04,05,06,13,15,21,23.

### 1.4 Two kinds of completion gates
CG code-complete (automated tests now) vs EG empirical (needs real data/time). EG mechanism is CG; outcome is EMPIRICAL_PENDING until evidence.

---

*Operator decisions override via config. Truth hierarchy governs conflicts.*
