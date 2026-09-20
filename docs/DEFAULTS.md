# docs/DEFAULTS.md — Mirrors config/default.yaml (Part 12) — canonical = YAML

All values are design defaults — not empirically validated unless census/validation says otherwise. Marked **HARD** = config may only make stricter (code change required to raise).

Copy of `config/default.yaml` with rationale (see file). Key tables:

| Group | Key | Default | Unit | Range | Rationale |
|-------|-----|---------|------|-------|-----------|
| time | clock_drift_warn_ms | 500 | ms | 0..5000 | NTP drift warn |
| time | clock_drift_block_ms | 2000 | ms | — | blocks new entries |
| freshness | quote_stale_after_s | 5 | s | — | HEALTHY→DEGRADED |
| freshness | quote_disconnected_after_s | 30 | s | — | →DISCONNECTED, stops entries |
| transport | ws_rotate_before_h | 23 | h | <24 | proactive before 24h limit |
| transport | rest_rate_budget_fraction | 0.5 | frac | 0..1 | use ≤50% of Binance budget |
| retention | candles_1m_days_pg | 400 | d | — | operational window |
| retention | disk_free_min_gb | 10 | GB | — | warn, <2 block P2 recorders |
| indicators | atr_period | 14 | bars | — | Wilder |
| regime | adx_min | 22 | — | — | trend threshold |
| ict.swing | left/right | 3 | bars | — | pivot needs R to confirm |
| ict.structure | min_break_atr | 0.10 | ATR | — | close beyond level |
| ict.displacement | body_to_range_min | 0.60 | ratio | 0..1 | |
| ict.fvg | min_size_atr | 0.15 | ATR | — | filter tiny gaps |
| strategy.ict_a | stop_buffer_atr | 0.25 | ATR | — | beyond sweep/zone |
| strategy.ict_a | tp1_r | 1.5 | R | — | partial 50% |
| signal | ttl_bars 15m | 8 | bars | — | expiry |
| costs | taker_fee_bps | 10 | bps | — | conservative |
| paper | latency_ms | 300 | ms | — | decision→fill |
| risk | risk_per_trade_pct | 0.25 | % | **HARD cap 0.50** | |
| risk | max_daily_loss_pct | 1.5 | % | **HARD cap 2.00** incl unrealised | |
| risk | max_trades_per_day | 6 | count | **HARD cap 10** | |
| risk | max_per_symbol_risk_pct | 0.5 | % | — | |
| locks | max_spread_bps | 15 | bps | — | spread lock |
| probability | min_train_events_effective | 100 | events | — | ±10% CI needs ~100 independents |
| probability | max_ci_halfwidth | 0.10 | — | — | |
| probability | max_ece | 0.05 | — | — | |
| backtest | random_entry draws | 200 | — | — | baseline harness |
| setup_score | weights htf 20 liq 20 etc | — | — | — | descriptive, never prob |

Full YAML in `config/default.yaml` (single source; test asserts docs==code).
