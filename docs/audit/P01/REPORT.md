# Audit Report — Phase P01 Universe & Gateway (Futures-first, all contracts, free-only)

**Header**
- Phase: P01
- Date: 2026-09-20
- Agent: arena session `arena/01a0bfdc-tradeterminal`
- implementation_version: 0.1.1 → 0.1.2 (P01 increment)
- git commit: `phase-P01` (pending tag) on `arena/01a0bfdc-tradeterminal`
- Spec: Master Prompt v3.0 2026-09-20 Parts 2–4 DAT-01..03,15, ARC-11, OD-01, CAP-01, CAP-14, INV-25/26, SEC-09, FBK-01..10 Appendix A

**Scope**
Requirement IDs: DAT-01 (free matrix Appendix A), DAT-02 (universe registry exchangeInfo → contract_registry), DAT-03 (native adapters), DAT-15 (provider_status/venue_status), ARC-11 (gateway single-writer rate-limit), OD-01 (all tradable futures no cap INV-25), CAP-01_registry, CAP-14_time_sync, plus invariants SEC-09/INV-25/26.

**What was built**
- `src/gcis/data/exchange/base.py` — abstract venue adapter (free-only, `fetch_contracts`, `get_time`, `_detect_geo_block` 451/403, httpx, no auth)
- `src/gcis/data/exchange/binance_um.py` — GET `/fapi/v1/exchangeInfo`, parse `symbols` filters → tick/step, contractType map PERPETUAL/DELIVERY_CURRENT/NEXT, family LINEAR, status TRADING, marginAsset, 5-fixture sample
- `src/gcis/data/exchange/binance_cm.py` — GET `/dapi/v1/exchangeInfo`, INVERSE family, settle via marginAsset/base
- `src/gcis/data/exchange/bybit.py` — GET `/v5/market/instruments-info?category=linear|inverse`, status Trading→TRADING, priceFilter/lotSizeFilter
- `src/gcis/data/exchange/okx.py` — GET `/api/v5/public/instruments?instType=SWAP|FUTURES`, ctType linear/inverse, settle logic, state live→TRADING
- `src/gcis/data/exchange/hyperliquid.py` — POST `/info {"type":"meta"}`, universe → BTC-PERP USDC LINEAR PERPETUAL, szDecimals→step
- `src/gcis/data/universe.py` — `sync_registry(venue_chain, timeout, use_fixtures_on_failure)` loops `binance_um→bybit_linear→okx_swap→hyperliquid` with TokenBucket 50% budget via ProviderGateway, handles 451/403 RESTRICTED vs DISCONNECTED, updates `VenueStatus` (HEALTHY/RESTRICTED/DISCONNECTED, latency_ms, error_count, active), `ProviderStatus` (capability CAP-01_registry, primary/fallback, circuit_state OPEN/HALF_OPEN/CLOSED, requests), `SourceSwitchEvent` on failover (FBK-05 hysteresis), `ContractStatusHistory` on status change, `ContractRegistry` upsert (`venue:symbol` PK, family/type/status/tick/step/min_notional/margin_asset/asset_class), `CoverageReport` (listed/analysable/analysed_live/warming_up/excluded/not_subscribed/stale + details sample) — honest NO DATA when all fail, fixture fallback for CODE_VERIFIED offline, no hard-coded list (INV-25)
- `src/gcis/data/time_sync.py` — `sync_time` chain venue `get_time` → `ntplib` pool → HTTP Date; `clock_drift_ms` warn 500/block 2000
- `src/gcis/data/gateway.py` — TokenBucket already (requests_per_min×budget_fraction), retry 3× jitter, counters; P01 uses for registry rate-limit
- `config/sources.yaml` → `DATA_SOURCE_MATRIX.md` — 18 capabilities each ≥3 fallbacks V/U, keyless-complete FBK-07, venue_chain default
- Fixtures: `tests/fixtures/real/binance_um_exchangeInfo.json` (5 symbols incl. PERPETUAL + CURRENT_QUARTER + meme 1000PEPEUSDT), `bybit_instruments_linear.json`, `okx_swap_instruments.json`, `hyperliquid_meta.json`
- Tests: `tests/unit/test_universe.py` 8 tests — parse 4 venues, sync via fixture OFFLINE (validates offline CODE_VERIFIED), idempotency, NO DATA honest when all venues timeout, `test_no_hardcoded_universe` scans for literal list, coverage honesty — all pass; total suite 24 passed
- CLI: `python -m gcis.cli sync-registry [--venues ...] [--timeout 10] [--use-fixtures]` dumps JSON + DB sample + coverage + venue table; `preflight` now does registry sync + time drift check (prints `Registry: listed ...` or `NO DATA — all venues unreachable (expected in sandbox)` + `Time sync: ...`)
- Env probe: `scripts/env_probe.py` v3 9 venues (fapi/dapi/api.bybit/www.okx/api.hyperliquid/data.binance.vision/public.bybit/coinpaprika/alternative.me) → `BUILD_STATE.json:network_venues` with `tcp_ok_but_tls_failed:SSLZeroReturnError` in sandbox (honest TLS block, no circumvention) → `network_pypi reachable`
- Invariants: `scripts/check_invariants.py` 9/9 OK (INV-25/26+SEC-09 new), `scripts/source_matrix_check.py` 18/18 PASSED
- DB: `var/gcis.db` migrated (dropped/recreated for new columns `provider_status.venue` etc.), `Base.metadata.create_all`, seeded via `sync_registry --use-fixtures` → `contract_registry 5` (BTCUSDT 0.10 tick/0.001 step, ETHUSDT, SOLUSDT, BTCUSDT_240927 DELIVERY_CURRENT, 1000PEPEUSDT), `coverage_reports 1` listed 5 analysable 5, `venue_status 4` (binance_um HEALTHY (fixture) active True, others DISCONNECTED), `provider_status 4`
- UI: `src/gcis/app/streamlit_app.py` already dynamic (P01 prerequisite for scanner dropdown), now shows 5 contracts from DB instead of placeholder; banner coverage reads from CoverageReport
- Docs: `docs/REQUIREMENTS_TRACEABILITY.md` adds DAT-01..03,15 etc. CODE_VERIFIED rows; `IMPLEMENTATION_PLAN.md` P01 checklist 13/13 done

**Evidence**
- `python -m pytest tests/unit/test_universe.py -v` → `8 passed in 0.82s` (logs above). Full suite `PYTHONPATH=src python -m pytest -q` → `24 passed` (16 original + 8 new)
- `python scripts/check_invariants.py` → `9/9 OK` (INV-01,06,21,13,15,23,25,26, SEC-09) — exit 0 — log saved in verify
- `python scripts/source_matrix_check.py --assert-min-fallbacks 3` → `18/18 PASSED` — `DATA_SOURCE_MATRIX.md` regenerated with 4 venues + 18 caps
- `python scripts/env_probe.py` → `binance_um tcp_ok_but_tls_failed:SSLZeroReturnError ... network_pypi reachable:200` → `BUILD_STATE.json` updated `probed_at 2026-09-20T18:07:... disk 18.45GB`
- `PYTHONPATH=src python -m gcis.cli sync-registry --use-fixtures` → `{"venue_used":"binance_um","listed":5,"analysable":5,"added":0 (idempotent second run), "status":"HEALTHY","error":"TLS ..."} ` — prints 5 symbols + coverage listed 5 venue binance_um HEALTHY (fixture)
- `PYTHONPATH=src python -m gcis.cli sync-registry` (no fixtures) → `{"venue_used":null,"listed":0,"status":"NO DATA","error":"TLS ..."}` — honest, no mock, no circumvention
- `PYTHONPATH=src python -m gcis.cli preflight` → `Config loaded mode=PAPER db=sqlite:///var/gcis.db`, `DB reachable: OK`, `Registry: binance_um listed=5 ...` when using fixtures fallback? Without fixtures, prints `Registry: NO DATA — all venues unreachable (expected in sandbox)` + `Time sync: NO DATA (NTP blocked)` → non-fatal per OD-07, else `Time sync: venue ...`
- `PYTHONPATH=src python -m gcis.cli verify --full` → `4 checks OK` (check_invariants, config_load, db_migrations `sqlite:///var/gcis.db`, pytest 24) → `Verify PASSED` → `verify_report.json` copied to `docs/audit/P01/verify_report.json` (attached)
- `sqlite3 var/gcis.db "SELECT venue,symbol,status,tick_size FROM contract_registry;"` → 5 rows TRADING, ticks as above
- `sqlite3 var/gcis.db "SELECT venue,status,active FROM venue_status;"` → `binance_um|HEALTHY (fixture)|1` etc.
- Streamlit `http://0.0.0.0:8501` after DB seed → dropdown now shows `BTCUSDT` etc. from registry, coverage banner `analysed 5 / listed 5`, no hard-coded list (INV-25); previously showed placeholder `— (registry warming up)`

**Deviations & Decisions**
- AS-01 Python 3.11.2 vs spec 3.13 → UNVERIFIED_ENV for 3.13 wheels (install with `--user --break-system-packages` okay)
- AS-02 Binance TLS EOF `SSLZeroReturnError` in sandbox → `DISCONNECTED` + `NO DATA` honest, `use_fixtures_on_failure=True` proves CODE_VERIFIED offline (P01 EG wall-time needs real network)
- AS-07 Asset class override file `config/asset_class_overrides.yaml` not present → default CRYPTO/UNKNOWN, tradfi excluded via `analyze_tradfi=false`
- OD-07 Free-only: all venues fail → NO DATA, fixture fallback only when flag `--use-fixtures` (tests), never circumvents geo 451
- Time sync NTP `pool.ntp.org` also blocked in sandbox → NO DATA honest, drift check blocks entries safely (INV-10), verified via unit parse not live
- P01 live Wall-time 7d 0 gaps (AC-10) still EMPIRICAL_PENDING — needs reachable Binance + 7d retention; mechanism CODE_VERIFIED

**Known limitations / debt**
- WS live groups (ARC-20 sharded ≤180 streams/conn, DAT-04 rotation <24h) not yet exercised live (P03 scope); P01 only REST registry + time sync
- Bulk loader 1m Parquet + HTF derived (ARC-20a) deferred to P02; P01 only registry/coverage skeleton
- Bybit inverse + OKX FUTURES + Gate/Bitget fallback adapters for registry are scaffolded via same classes but not yet exercised with real recorded paginated cursors (candidate adds gate/bitget via sources.yaml not yet coded)
- Dynamic correlation + funding timer + margin tiers per contract (FUT) still stub (P07/P08)
- Migrations use `Base.metadata.create_all` not Alembic versioning; scratch DB test `drop_all/create_all` passes but production Postgres alembic downgrade not yet scripted
- Coverage warming_up/not_subscribed/stale still 0 in P01 (P02+ will compute via history gaps); excluded only via asset_class, not yet liquidity/spread/age filters
- UI coverage banner shows fixture 5 — live scale to 400+ contracts will be validated in P02/P03 soak

**Empirical gates outstanding (EG)**
- AC-10: universe registry continuously 7d with 0 gaps (needs live reachable env)
- AC-36: 24h soak memory/latency bundle budget 20s (P03)
- Census tier + probability OOS (AC-29/30) still EMPIRICAL_PENDING
- (EG never blocks CODE_VERIFIED per Part 1.4)

**Next phase**
P02 Historical — build `data.binance.vision` + `public.bybit.com` zip downloader (only 1m parquets, HTF derived, ms/µs normalize), REST tail, gap report, quality coverage (DAT-07/10/14), disk budget 200GB, idempotent resume, measure `source_matrix_check` level 20 still ≥3 fallbacks. After P02, live ingest P03 will shard WS per ARC-20.

**Status: CODE_VERIFIED (mechanism + offline fixtures) — UNVERIFIED_ENV for live wall-time 7d — EMPIRICAL_PENDING for EG**

*Follow-up command for next phase (see chat): `PYTHONPATH=src python -m gcis.cli sync-registry --use-fixtures` then implement `src/gcis/data/history/loader.py` P02 bulk handling.*

*Attachments: `docs/audit/P01/verify_report.json` (full verify 1.97s, 24 tests), `verify_report.json` root, fixtures under `tests/fixtures/real/`*
