# Audit Report — Phase P19 Consolidation (P1/P2)

**Header**
- Phase: P19
- Date: 2026-09-20
- Agent: arena session `arena/01a0bfdc-tradeterminal`
- implementation_version: 0.1.20
- git branch: arena/01a0bfdc-tradeterminal
- Verify command: `PYTHONPATH=src python -m gcis.cli verify --full`

**Scope**
Requirement IDs: DAT-16 (trade archive), BKT-11 (paper-vs-backtest consistency), plus funding/leverage consistency stubs. Out-of-scope P20-P22/P99.

**What was built**
- `src/gcis/data/archive/trade_archive.py` — DAT-16 trade archive. `TRADE_ROOT var/trade_archive`, `trade_path(venue/symbol/day.jsonl)`, `append_trades(venue,symbol,trades)` dedup by aggTradeId, list/purge 30d, stats. Free-only, no overwrite, retention 30d vs candles unlimited.
- `src/gcis/backtest/consistency.py` — BKT-11 paper-vs-backtest consistency. `compare_paper_backtest(paper_trades, backtest_trades, threshold 15 bps)` avg pnl bps divergence flag CONSISTENT/DIVERGED, `funding_consistency_check` ratio vs 0.15R, `effective_leverage_consistency` cap 3. Deterministic.
- `tests/unit/test_consolidation_p19.py` — 3 tests: trade archive append dedup 2→3 lines same file stats, purge 40d old, backtest consistency 7.5 bps consistent then 490 bps diverged + funding/leverage, no forbidden strings.

**Evidence**
- Command: `PYTHONPATH=src python -m pytest tests/unit/test_consolidation_p19.py -v` → **3 passed** 0.04s
- Command: `PYTHONPATH=src python -m pytest tests/unit -q` → **185 passed** 1 warning (182 P18 +3 =185).
- Command: `PYTHONPATH=src python -m gcis.cli verify --full` → 4 checks OK: check_invariants 9/9, config_load, db_migrations, pytest 185 dots PASSED → `verify_report.json` + `docs/audit/P19/verify_report.json`
- Manual: append 2 ids then duplicate no new lines proves dedup; divergence 7.5 <15 consistent proves BKT-11 logic.

**Deviations**
- Trade archive uses aggTradeId dedup, not tick-level sequence; real DAT-16 would also store firstTradeId/lastTradeId range but P19 stub covers idempotency.
- Consistency threshold 15 bps per BKT-11; real paper vs backtest would also compare distribution (Kolmogorov) deferred to P20.

**Known limitations**
- Trade archive not yet wired to live aggTrade WS; will be P20 with depth.
- Funding realized requires live funding rate feed; currently static stub.

**Empirical gates**
- Real trade archive needs 30d live aggTrade ingest — synthetic only.
- Paper vs backtest needs 100 trades each for stable bps — synthetic only.

**Next phase**
P20 — Remaining: scale final / backtest census final / audit prep. Update `BUILD_STATE.json current_phase=P20`.

**Status: CODE_VERIFIED (185 tests, 9 invariants, 18 caps) — P19 DAT-16 + BKT-11 verified — DOCS==CODE**

*Format Part 13.3; evidence at `docs/audit/P19/verify_report.json`.*
