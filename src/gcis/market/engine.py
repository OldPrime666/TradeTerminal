"""
Market engine P04 — in-house feature engine, MarketView builder, regime, sessions.
Causal only, deterministic, no look-ahead (INV-04).
"""
from datetime import datetime, timezone
from typing import Dict, Any
import pandas as pd
from gcis.market.indicators import (
    sma, ema, rsi_wilder, atr_wilder, adx_wilder, bollinger,
    efficiency_ratio, vwap_anchored, rolling_volume_median
)
from gcis.market.regime import compute_regime
from gcis.market.view import MarketView

def build_market_view(
    candles: Dict[str, Dict[str, pd.DataFrame]],
    quotes: Dict[str, dict],
    as_of: datetime,
    config: dict | None = None,
) -> MarketView:
    """
    Build causal MarketView as_of.
    candles: symbol -> timeframe -> DataFrame with columns open_time, close_time, open, high, low, close, volume etc.
    quotes: symbol -> {price, updated_at, source}
    config: global config (for regime thresholds). If None, uses defaults from config/default.yaml.
    Returns MarketView with closed candles filtered (close_time <= as_of), features computed only on closed data, regimes.
    """
    if config is None:
        try:
            from gcis.core.config import get_config
            config = get_config()
        except Exception:
            config = {}
    # Filter candles to closed (as_of)
    filtered: Dict[str, Dict[str, pd.DataFrame]] = {}
    features: Dict[str, dict] = {}
    regimes: Dict[str, dict] = {}
    for symbol, tf_map in candles.items():
        filtered[symbol] = {}
        features[symbol] = {}
        regimes[symbol] = {}
        for tf, df in tf_map.items():
            if df is None or df.empty:
                filtered[symbol][tf] = df
                continue
            # Filter closed candles only
            # df close_time should be timezone-aware UTC
            # Ensure as_of is UTC
            if as_of.tzinfo is None:
                as_of = as_of.replace(tzinfo=timezone.utc)
            # Filter
            closed = df[df["close_time"] <= as_of].copy()
            filtered[symbol][tf] = closed
            # Compute features only on closed (causal)
            if not closed.empty:
                # Convert to float series for indicators
                close_s = closed["close"].astype(float) if "close" in closed.columns else pd.Series(dtype=float)
                high_s = closed["high"].astype(float) if "high" in closed.columns else pd.Series(dtype=float)
                low_s = closed["low"].astype(float) if "low" in closed.columns else pd.Series(dtype=float)
                vol_s = closed["volume"].astype(float) if "volume" in closed.columns else pd.Series(dtype=float)
                # Compute indicators incrementally (rolling)
                # Store last values for MarketView features
                try:
                    ema9 = ema(close_s, 9)
                    ema21 = ema(close_s, 21)
                    ema50 = ema(close_s, 50)
                    rsi = rsi_wilder(close_s, 14)
                    atr = atr_wilder(high_s, low_s, close_s, 14)
                    adx, plus_di, minus_di = adx_wilder(high_s, low_s, close_s, 14)
                    mid, upper, lower, bw = bollinger(close_s, 20, 2.0)
                    er = efficiency_ratio(close_s, 20)
                    vol_med = rolling_volume_median(vol_s, 20)
                    # Keep last value
                    features[symbol][tf] = {
                        "ema9": float(ema9.iloc[-1]) if not ema9.empty and not pd.isna(ema9.iloc[-1]) else None,
                        "ema21": float(ema21.iloc[-1]) if not ema21.empty and not pd.isna(ema21.iloc[-1]) else None,
                        "ema50": float(ema50.iloc[-1]) if not ema50.empty and not pd.isna(ema50.iloc[-1]) else None,
                        "rsi": float(rsi.iloc[-1]) if not rsi.empty and not pd.isna(rsi.iloc[-1]) else None,
                        "atr": float(atr.iloc[-1]) if not atr.empty and not pd.isna(atr.iloc[-1]) else None,
                        "adx": float(adx.iloc[-1]) if not adx.empty and not pd.isna(adx.iloc[-1]) else None,
                        "bb_bandwidth": float(bw.iloc[-1]) if not bw.empty and not pd.isna(bw.iloc[-1]) else None,
                        "efficiency_ratio": float(er.iloc[-1]) if not er.empty and not pd.isna(er.iloc[-1]) else None,
                    }
                except Exception:
                    # If insufficient history, leave features empty
                    features[symbol][tf] = {}
                # Regime per symbol (using the same closed df)
                try:
                    regime_res = compute_regime(closed, config)
                    regimes[symbol][tf] = {
                        "trend": regime_res.trend_regime,
                        "vol": regime_res.vol_regime,
                        "flags": regime_res.flags,
                        "agreement": regime_res.agreement,
                        "evidence": regime_res.evidence,
                    }
                except Exception:
                    regimes[symbol][tf] = {"trend": "UNCERTAIN", "vol": "NORMAL", "flags": [], "agreement": 0.0, "evidence": ["REGIME_FAILED"]}
            else:
                features[symbol][tf] = {}
                regimes[symbol][tf] = {"trend": "UNCERTAIN", "vol": "NORMAL", "flags": [], "agreement": 0.0, "evidence": ["NO CLOSED CANDLES"]}
    # Filter quotes to as_of (only quotes with updated_at <= as_of)
    filtered_quotes: Dict[str, dict] = {}
    for sym, q in quotes.items():
        upd = q.get("updated_at")
        if upd is None:
            continue
        if upd.tzinfo is None:
            upd = upd.replace(tzinfo=timezone.utc)
        if upd <= as_of:
            filtered_quotes[sym] = q
    # Build view
    view = MarketView(
        as_of=as_of,
        candles=filtered,
        quotes=filtered_quotes,
        features=features,
        regimes=regimes,
    )
    return view
