# OPERATIONS.md — Runbook (OPS-11)

## Alerts & states — meaning, confirm, fix, verify

| Alert | Meaning | Confirm | Fix | Verify |
|-------|---------|---------|-----|--------|
| **STALE** | Last update older than freshness thresholds (quote 5s, candle 2 bars+5s) | System Health → candle age, provider last_success | Check network, Binance WS state, `healthcheck.bat`, logs `var/logs/` | Health → `HEALTHY`, new candle persisted |
| **DISCONNECTED** | WS + polling both failed >30s | `provider_status` = DISCONNECTED, `last_failure` recent | `python -m gcis.cli preflight` (checks `/api/v3/ping`, `/api/v3/time`), wait backoff, no manual loops | Health `WEBSOCKET` recovered, gap backfill log |
| **MARKET_DATA_DISCREPANCY** | Secondary provider (CoinPaprika/CoinLore) disagrees > flag bps and both fresh ≤900s | `provider_status` shows both HEALTHY, `canonical_value` vs `secondary_value` diff | No trade blocked by itself — record only; if persistent, check secondary health | Status `HEALTHY` when within warn bps |
| **UNRESOLVED_GAP** | Missing candles/history that cannot be backfilled (network + REST failed) | Data-quality report shows gap, position flagged | `python -m gcis.cli download-history`, verify archive; block new entries until reviewed | Gap report 0 missing |
| **KILL_SWITCH_ACTIVE** | `kill_switch_state.active=true` | Risk Center shows ⛔ | Manual unlock button (writes new row, audit) | Risk Center `ACTIVE`, verify no duplicate intent |
| **DAILY_LOSS_LOCK** | `daily_drawdown ≥ max_daily_loss_pct` (includes unrealised) | DailyRiskState `risk_lock=BLOCK_NEW_TRADES` | Wait until 00:00 UTC reset (OD-04) or manual unlock via DB if needed (logged) | Next risk day `ACTIVE` |
| **PROCESS_FAILED** | Supervisor restart >5 in 10min → `FAILED` | `worker_state.state=FAILED`, UI System Health | Check logs, `healthcheck.bat`, restart via `start.bat` | Worker `HEALTHY`, heartbeat ≤5s |
| **DB_UNREACHABLE** | PG/SQLite write fail | `system_health.db_ok=false` | Check disk free (`disk_free_min_gb` 10), file locks, restart | `preflight` DB OK |
| **MIGRATION_MISMATCH** | Code head ≠ DB head | `preflight` reports mismatch | `alembic upgrade head` (scratch verify first) | `preflight` green |
| **CLOCK_DRIFT** | Local vs exchange /time >500ms warn, >2000ms block | `preflight` shows drift | NTP sync, `drift_check_interval_s` 300s | Drift <500ms |
| **DISK_LOW** | <10GB warn, <2GB block P2 recorders | `healthcheck` + OS `df -h` | Rotate `var/raw` (>14d), archive segments, `backup.bat` | Free >10GB |

## Commands
```bash
python -m gcis.cli preflight          # startup self-check (OPS-03)
python -m gcis.cli healthcheck        # JSON verdict
python -m gcis.cli verify --post-install  # green before claiming deployed (0.8)
python -m gcis.cli download-history --symbols BTCUSDT ETHUSDT --timeframe 1m
python -m gcis.cli backtest --symbols BTCUSDT --timeframe 15m
python -m gcis.cli census
python scripts/env_probe.py
python scripts/check_invariants.py
python scripts/replay_verify.py      # >20 signals recomputed, evidence_hash equal
```

## Backup / Restore (OPS-06)
```bat
backup.bat               # pg_dump custom + config copy + Parquet manifest, verify via scratch restore
backup.bat --include-archive
python -m gcis.cli backup --verify
```
Retention per Part12; retention jobs chunked (ARC-17), never delete referenced by open position / unexpired signal / oos_lock.

## Resets (OPS-07, guarded)
```bat
reset_paper.bat          # needs typed "RESET PAPER", refuses while alive, refuses if live.enabled unless --i-understand-live, takes backup unless --no-backup, audit logged
reset_research_db.bat    # "RESET RESEARCH"
reset_database.bat       # "RESET DATABASE"
```
Normal start never drops data (INV-17).

## Supervisor (OPS-01)
`gcis.runtime.supervisor` starts ingest/core/slow/ui, exponential backoff 1s→60s+jitter, crash-loop breaker (>5/10min → FAILED), PID files, clean shutdown on Ctrl-C (flush, commit cursors, close WS, write worker_state). Windows uses `CREATE_NEW_PROCESS_GROUP`.

## Logs
`logs/*.jsonl` rotating, structured `{timestamp, component, level, event, symbol, market_type, job_id, signal_id, trade_id, message}` with secret redaction (tested).
