# Audit Report — Phase P15 Hardening II (P1)

**Header**
- Phase: P15
- Date: 2026-09-20
- Agent: arena session `arena/01a0bfdc-tradeterminal`
- implementation_version: 0.1.16
- git branch: arena/01a0bfdc-tradeterminal
- Verify command: `PYTHONPATH=src python -m gcis.cli verify --full`

**Scope**
Requirement IDs: VOL-01 (volume profile), PSY-01 (proxies), Notifications (OPS-10), RSK-04 integration into RiskManager (per-cluster + per-strategy + news/psy veto). Out-of-scope P16-P22/P99.

**What was built**
- `src/gcis/market/volume_profile.py` — VOL-01. `compute_volume_profile(candles, bins 24, value_area_pct 0.70)` histogram price by volume, POC max volume bucket, value area contiguous expansion from POC until 70% total, profile list with low/high/mid/volume, total_volume, bins, note. Handles NO_DATA/NO_RANGE/NO_VOLUME. Deterministic, uses close for binning.

- `src/gcis/psychology/proxies.py` — PSY-01. `compute_psy_proxies(closes, volumes, period 20)` returns volatility std* sqrt(35040) ann, neg_ratio, max_drawdown, fear_greed 0-100 (vol*5000 + neg_ratio*30 + dd*40 centered 50), psy_regime RISK_OFF (>70 fear & ann_vol>0.8) / RISK_ON (<30 & <0.5) / NEUTRAL, vol_spike vs avg, `psy_veto` advisory (blocked false for paper per config). INSUFFICIENT_HISTORY when <25 closes. Alternative.me deferred.

- `src/gcis/ops/notifications.py` — Notifications rate-limited queued. `NotificationManager` max_per_min 10 queue_max 100, deque sent_times, `_allow_send` counts last 60s, `enqueue` drops oldest if full, `flush` logs to `var/logs/notifications.jsonl` respecting limit, `send_now` immediate, singleton `get_notification_manager` + `notify` helper. Never leaks secrets, chunked.

- `src/gcis/risk/manager.py` — RSK-04 integration (P15). Added per-cluster check (supports float and dict per_cluster_risk), max_per_cluster_risk_pct 1.0 via `intent cluster_id` would exceed, per-strategy max_per_strategy 1.0, news veto `news_veto_blocked` => NEWS_BLACKOUT, psy veto conditional on `psychology.block_on_psy_risk_off`. Existing hard caps retained. Enhances check to use correlation clusters.

- `tests/unit/test_hardening2_p15.py` — 8 tests: volume_profile POC within 99-101 and VA contains POC and NO_DATA, no_range, psy proxies fear low vs high and veto not blocking, insufficient, notifications rate limit 2/min flush and second minute, risk manager cluster dict exceed and news veto, per_strategy, no forbidden strings.

**Evidence**
- Command: `PYTHONPATH=src python -m pytest tests/unit/test_hardening2_p15.py -v` → **8 passed** 0.04s — all VOL/PSY/notifications/risk integration deterministic.
- Command: `PYTHONPATH=src python -m pytest tests/unit -q` → ` ........................................................................ [45%]` + `........................................................................ [90%]` + `................ [100%]` **160 passed** 1 warning 12.66s (152 P14 +8 =160).
- Command: `PYTHONPATH=src python -m gcis.cli verify --full` → 4 checks OK: check_invariants 9/9 (INV-01 06 21 13 15 23 25 26 SEC-09), config_load, db_migrations `sqlite:///var/gcis.db`, pytest 160 dots PASSED → `verify_report.json` + `docs/audit/P15/verify_report.json` (all_ok true).
- Manual: `compute_volume_profile` POC 100.5 proves histogram; `compute_psy_proxies` steady up fear < volatile down; `NotificationManager` 3 enqueue flush 2 rate_limited true validates limit; `RiskManager` cluster 0.9+0.25>1.0 blocked proves integration.

**Deviations & Decisions**
- Volume profile uses close for binning (typical price optional) to keep deterministic without aggTrades tick data; DOM depth will enhance with real bid/ask later.
- Psy proxies purely price-action derived (no external alternative_me call) to stay free-only keyless; fear 0-100 centered 50 with vol*5000 scaling tuned to keep 30 max.
- Notifications log to jsonl file not external webhook to keep free and no secret leakage; rate limit prevents spam (max 10/min).
- Risk manager cluster check accepts both float and dict to remain backward compatible with previous exposure shapes.

**Known limitations / debt**
- VOL aggTrades real volume profile from trade-by-trade (DAT-16) still stub; current uses candle volume.
- PSY alternative_me Fear&Greed live fetch via budgets not yet wired; proxy remains price-based.
- Notifications webhook (Telegram/Discord) not yet configured; only log channel.
- Future DOM orderbook engine (P3) not included.

**Empirical gates outstanding (EG)**
- Real VOL profile needs 24h of 1m candles with volume (needs archive populated) — currently synthetic.
- PSY proxies need 30d of 1h returns for meaningful regime — synthetic tests only.
- Notifications delivery needs real webhook credentials — currently log stub.
- Risk cluster integration needs real dynamic correlation from 30d returns — synthetic tests pass but live wall-time pending.

**Next phase**
P16 — Next Hardening / Scalability (ARC-20 sharded WS prioritised scheduling + bundle budget or DOM stub). Update `BUILD_STATE.json current_phase=P16`.

**Status: CODE_VERIFIED (160 tests, 9 invariants, 18 caps) — P15 Hardening II VOL-01 + PSY-01 + notifications + RSK-04 integration verified — DOCS==CODE**

*Format Part 13.3; evidence at `docs/audit/P15/verify_report.json`. P15 = VOL + PSY + notifications + risk integration.*
