# ICT Definitions — P05 ICT Core (ICT-01..13)

> **Source of truth:** `config/default.yaml` (`ict:` block) + `src/gcis/ict/*.py`.  
> This file mirrors code thresholds; `scripts/check_invariants.py` or `test_ict_p05::test_docs_eq_code` asserts docs==code.

## ICT-01 Swings (src/gcis/ict/swings.py::detect_swings)
- `L=R=3` (left/right bars): swing HIGH ⇔ `high[p] > high[p-k]` ∀ k=1..L (strict left) and `high[p] ≥ high[p+k]` ∀ k=1..R (non-strict right). LOW mirrored: `low[p] < low[p-k]` strict left, `≤` right.
- `min_strength_atr 0.5`: prominence/ATR ≥0.5 where prominence = `hp - max(neighbour highs)` (HIGH) or `min(neighbour lows)-lp` (LOW). Measured at `ATR@confirmation` (Wilder 14). Warmup NaN skips filter.
- `min_separation_bars 3`: pivots of same type within <3 bars are not independent; causal keep-first (earlier confirmed swing kept, later discarded; no retroactive invalidation → no repaint).
- Causal: CONFIRMED only after `p+R` closes (`confirmation_at = close_time[p+R]`). Deterministic. Status `CONFIRMED` → `BROKEN` by ICT-02, never deleted.
- IDs `symbol-timeframe-H|L-p`.

## ICT-02 Structure BOS/CHOCH (src/gcis/ict/structure.py::detect_structure)
- `break_on close`, `min_break_atr 0.10`: close must exceedSwing level + `0.10*ATR` (up) or below - buffer (down). Uses ATR of break bar.
- Bias `UNDEFINED` until at least 2 HIGH +2 LOW swings. Initial bias from last two swings: `H[-1]>H[-2] && L[-1]>L[-2]` → BULLISH, opposite → BEARISH else UNDEFINED.
- Levels: latest confirmed unbroken swing HIGH/LOW whose `confirmation_at ≤ break_bar_time` (causal). Stack maintained; broken level removed.
- BOS vs CHOCH: if prior bias BULLISH/UNDEFINED + upside break → BOS BULL else CHOCH_BULL (flip). Mirror for downside. Event `type` BOS or CHOCH_BULL/CHOCH_BEAR.
- Marks swung BROKEN, deterministic, no repaint.

## ICT-03 Displacement (src/gcis/ict/displacement.py)
- `body_to_range_min 0.60`, `range_atr_min 1.5`, `close_position_min 0.70`, `min_consecutive 1`
- `range=high-low`, `body=|close-open|`, `body/range ≥0.60` and `range ≥1.5*ATR`
- Bullish: `(close-low)/range ≥0.70` (close in upper 70%); Bearish: `(high-close)/range ≥0.70` (close near low, i.e. `(close-low)/range ≤0.30`).
- Causal per bar; `find_displacements` returns indices.

## ICT-04 FVG (src/gcis/ict/fvg.py::detect_fvgs)
- 3-bar `i-2,i-1,i`: `low[i] > high[i-2]` → BULL FVG zone `[high[i-2], low[i]]`; `high[i] < low[i-2]` → BEAR opposite.
- `min_size_atr 0.15`, `min_size_ticks 2` with `tick_size 0.01` → `gap ≥ max(0.15*ATR, 2*tick)`.
- Displacement filter: if `displacement_indices` supplied, middle `i-1` must be displacement else skip.
- `max_age_bars 200`, `mitigation 50pct_or_full` handled by ICT-07.
- Created at `close_time[i]`, causal; `size_atr = gap/ATR`, `status FRESH`.

## ICT-05 Order Block (src/gcis/ict/order_blocks.py::detect_order_blocks)
- `displacement_within_bars 3`, `require_bos true`, `max_age_bars 300`, `use_body_zone true`
- Bullish OB = last bearish candle (`close<open`) before bullish displacement + BOS/CHOCH_BULL within `displacement_within_bars`. Zone = body `[min(open,close), max(open,close)]` if `use_body_zone` else `[low,high]`. Bearish opposite.
- Must have displacement in window `[break_idx-3, break_idx]` and linked `structure_event` (require_bos). Age invalidation via ICT-07.
- `created_at = break_time`, causal.

## ICT-06 Liquidity / Sweeps (src/gcis/ict/sweeps.py::detect_sweeps)
- `equal_level_tolerance_atr 0.10`, `min_touches 2`, `lookback_bars 100`
- Equal level: cluster of ≥2 highs/lows within `tolerance = 0.10*ATR` in lookback ahead of sweep. Causal: level built from bars before sweep bar.
- `sweep.penetration_min_atr 0.05`, `reject_within_bars 3`, `wick_based true`, `require_displacement true`
- Sweep of highs (BEAR): `high > level + 0.05*ATR` and `close < level` (close back inside). Sweep of lows (BULL) opposite. Needs displacement within next 3 bars if required.
- Fallback: if no equal level, uses rolling 20-bar max/min as level (for synthetic). Status `CONFIRMED` only when all criteria met.
- IDs `sweepH/sweepL`, `level_type EQUAL_HIGH/LOW or SWING_*`.

## ICT-07 Mitigation (src/gcis/ict/mitigation.py)
- FVG: `max_age_bars 200` → INVALIDATED if not touched within 200. `mitigation 50pct_or_full`: MITIGATED when `low ≤ midpoint` (50%) or `close ≤ lower` (bear opposite). TOUCHED when wick enters zone.
- OB: `max_age_bars 300`. BULL OB touched when `low ≤ zone_high`. Mitigated when `low ≤ midpoint` (50% of OB) + displacement away within 3. TOUCHED vs MITIGATED.
- Forward scan causal from `created_index/break_index+1`. Once MITIGATED/INVALIDATED persists.

## ICT-08 Breaker (src/gcis/ict/breaker.py::detect_breakers)
- `lookahead_bars 50`, `min_break_atr 0.10` buffer.
- Breaker = failed OB that after mitigation (or fresh) is broken opposite with displacement.
  Bull OB → bear breaker when `close < zone_low - 0.10*ATR` with displacement; bear OB → bull breaker when `close > zone_high + buffer`.
- Searches `break_index+1 .. +50` causally; confirmed on break close with displacement.
- Direction flips: `breaker.direction = opposite of source OB`. Status `ACTIVE`.

## ICT-09 Premium / Discount OTE (src/gcis/ict/premium.py)
- `ote_low 0.62`, `ote_high 0.79`, `require_discount_for_long true`, `require_premium_for_short true`
- Dealing range `low = min low of last 20`, `high = max high of last 20` (or last swing pair). `eq = (low+high)/2`
- Premium if `price > eq`, Discount if `price ≤ eq`.
- OTE zones: `long OTE = high - 0.79*range .. high -0.62*range` (≈ low+0.21 .. low+0.38), `short OTE = low +0.62*range .. low+0.79*range`. Check `price in zone`.
- `check_premium_discount(price, low, high, direction)` returns pass unless premium for long / discount for short and flags enabled.

## ICT-10 HTF/LTF Policy (src/gcis/ict/htf.py::check_htf_ltf_alignment)
- `htf_ltf_conflict_policy NO_TRADE`
- HTF bias BULLISH → only LONG allowed; BEARISH → only SHORT; UNDEFINED → allow. Mismatch → `HTF_LTF_CONFLICT` block.

## ICT-11 Relative Units
- All thresholds in ATR or ticks (relative), never absolute price/times. Tick via `tick_size 0.01` fallback.

## ICT-12 Golden + No-Repaint (tests/unit/test_ict_p05.py)
- Each detector has hand-built golden case producing expected IDs and a prefix vs full no-repaint test (early swings/events identical when truncated before future oracle spike). Oracle forward spike (1000) after 350 does not affect detections ≤300.

## ICT-13 Docs==Code (tests/unit/test_ict_p05.py::test_docs_eq_code)
- Asserts `config/default.yaml` ict thresholds equal this file and `src/gcis/ict` defaults (0.60,0.15,3,0.5,0.10 etc). CI fails if drift.

*Last verified 2026-09-20 P05 — run `PYTHONPATH=src python -m pytest tests/unit/test_ict_p05.py -v` 18 tests.*
