# DECISIONS.md — Operator Decisions (OD-xx) + Agent Assumptions (AS-nn)

## OD-xx (operator-decision defaults; override in config)
- OD-01: Universe BTC ETH SOL XRP DOGE BNB ADA AVAX LINK TON SUI PEPE → Binance Spot <BASE>USDT (resolved via exchangeInfo; missing/TRADING!=eligible → excluded)
- OD-02: Fees 10 bps/side (conservative placeholder)
- OD-03: Session windows Part 12 Asia/London/NY + killzones (not validated)
- OD-04: Risk day 00:00 UTC
- OD-05: Paper 10,000 USDT
- OD-06: DB local PostgreSQL preferred; SQLite fallback `sqlite:///var/gcis.db` for sandbox/local without Postgres
- OD-07: Binance public market data only; if blocked → NO DATA (never circumvent)
- OD-08: Live disabled ENABLE_LIVE_TRADING=false (LIVE-01)
- OD-09: Paper AUTO (EXPERIMENTAL while probability N/A); Live SEMI_AUTO

## AS-nn (agent assumptions made without blocking)
- AS-01: Python 3.11.2 in sandbox accepted (spec prefers 3.13, allows 3.12); marked UNVERIFIED_ENV for 3.13 wheel status — app remains compatible via tzdata.
- AS-02: Binance TLS failure in sandbox → transport state DISCONNECTED, polling fallback also fails → provider_status UNAVAILABLE → NO DATA displayed honestly. No mock price injected (INV-01).
- AS-03: Postgres not available → use SQLAlchemy SQLite with same schema (NUMERIC(38,18) via SQLite affinity, UTC timestamps as ISO). Postgres-specific LISTEN/NOTIFY replaced by polling in slow path (ARC-04 simplified).
- AS-04: Tick/step/minNotional for PEPE etc loaded dynamically from exchangeInfo at first successful connection; until then defaults used (0.01 tick, 1.0 step).
- AS-05: FVG/OB tick size default 0.01 until universe_registry provides real filter.
- AS-06: VWAP anchored to UTC day per IND-02; session-anchored variant deferred to P12.
- AS-07: News sources initially NONE (news veto disabled) → NEWS UNAVAILABLE state, no impact on non-news strategies (DAT-13).
- AS-08: Probability display gate at L0-L2 intentionally hides probability (PRB-12) → TOP UNVALIDATED CANDIDATE styled separately, ranked by setup score.
