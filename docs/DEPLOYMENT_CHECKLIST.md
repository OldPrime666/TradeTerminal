# DEPLOYMENT_CHECKLIST.md — What “deployed” means (0.8)

> Highest status a build agent can claim is **M0 CODE COMPLETE — EMPIRICAL VALIDATION PENDING** (P0 CODE_VERIFIED). `PRODUCTION READY` only via Live Readiness Report after real-world weeks.

## Prereqs (Windows 10/11 — Windows-first, cross-platform ARC-16)
- [ ] Python 3.13.x (verify) or 3.12/3.11 acceptable with `UNVERIFIED_ENV` flag for wheels
- [ ] `tzdata` installed (Windows has no system tz DB)
- [ ] PostgreSQL (currently supported major; verify) **or** SQLite fallback `var/gcis.db` (auto-created)
- [ ] 10 GB free disk (PART 12 `disk_free_min_gb`)
- [ ] Outbound to `data-api.binance.vision` + `data-stream.binance.vision` (if blocked → NO DATA is honest, not a crash)

## Steps
1. `git clone <repo>` → `cd GlobalCryptoICTScanner`
2. `install.bat` (or `install.sh` on Linux/sandbox)
   - Creates `var/`, `logs/`, installs pinned deps (`requirements.in` → lockfile hashes), runs `preflight`
   - Expect: `Config loaded`, `DB reachable: OK`, `Timezone DB: OK`, `Disk free ...`
   - If Binance `unreachable → NO DATA mode` → **honest**, not failure (OD-07)
3. `start.bat` (or `./start.sh` → 0.0.0.0:8501 for preview)
   - Runs `preflight`, then `streamlit run src/gcis/app/streamlit_app.py --server.address 127.0.0.1 --server.port 8501`
   - Check banner: `Mode: PAPER`, `Data: HEALTHY/DEGRADED/DISCONNECTED`, `DB: OK`, transport `WEBSOCKET/POLLING/NO DATA`
4. UI shows real Binance data? (if reachable)
   - Health → `HEALTHY`, provider `binance` `HEALTHY`, at least one closed candle per timeframe persisted
   - If sandbox/geo-blocked → `DEGRADED` + `NO DATA` per symbol → **expected** (see env_probe)
5. `healthcheck.bat` → JSON `{"verdict":"HEALTHY"|"DEGRADED", ...}` (exit 0)
6. `verify.bat --post-install` → `verify_report.json` green
   - Runs invariant scanner, import-linter, config, DB migrations, unit+property+golden tests, integration (scratch DB)
   - Live data flowing 60s + one closed candle per timeframe (if network available; else `UNVERIFIED_ENV` for live checks)

## What healthy looks like
- Banner `GLOBALCRYPTOICTSCANNER 2026 | Mode:PAPER | Data:HEALTHY | Risk:ACTIVE | DB:GCIS | Market:SPOT | v0.1.0`
- Overview → `STRONGEST SIGNAL` = `NO QUALIFIED SETUP` (with per-symbol reasons) at L0-L2 is **valid**; `TOP UNVALIDATED CANDIDATE` separately styled, probability `N/A — INSUFFICIENT_PROBABILITY_DATA`
- Scanner table sorted qualified→EV_lcb→score (never fabricated prob), lineage `source·timestamp·age·quality` visible
- Coin detail → price `source Binance · age 182ms · HEALTHY` with Plotly candles + VWAP/EMAs (from engine state, capped 800)
- Risk Center → equity/daily PnL/drawdown, risk lock `ACTIVE`, kill switch button works atomically (INV-10)
- System Health → all `HEALTHY`, metrics (messages_received, stale_events, analysis_cycles, …)

## Verify evidence (required for any status claim)
- `BUILD_STATE.json` → `environment.probed_at`, `last_verify`
- `verify_report.json` + `docs/audit/<phase>/verify_report.json` with command, exit code, timestamp, raw output
- `docs/audit/<phase>/REPORT.md` per 13.3 (scope, evidence, deviations, limitations, EG outstanding, next phase, Status vocabulary)
- No hard-coded prices/signals/probabilities/PnL (INV-01), no `TODO` in `src/`

## When Binance unreachable (sandbox/geo)
- Preflight → `unreachable → NO DATA mode`
- UI → `NO DATA` per symbol, scanner `NO DATA`, coin detail `NO DATA — ...`, health `DEGRADED`
- `verify --post-install` → live checks `UNVERIFIED_ENV` (honest, not failure)
- **Do not** mock prices (INV-01). Paper trading blocked until `HEALTHY` quotes (EXE).

## Rollback
- Supervisor crash-loop breaker → `FAILED` after >5 restarts/10m, visible in UI, no infinite loop
- `backup.bat` before any reset; resets require typed confirmation + audit
