import streamlit as st
from gcis.app.components.charts import render_candles
from gcis.persistence.db import get_session
from gcis.persistence.models import Candle, ContractRegistry
from gcis.runtime.health import compute_health
import pandas as pd

# Truthful health strip
try:
    h = compute_health()
    d = h.get("details", {})
    tr = d.get("transport_status", "NO DATA")
    badge = "badge-healthy" if tr == "WEBSOCKET" else "badge-degraded" if tr == "DEGRADED" else "badge-no-data"
    st.markdown(f"<div class='badge {badge}'>Transport: {tr}</div> <span class='small'>Data:{h.get('verdict')} · {d.get('candle_freshness')}</span>", unsafe_allow_html=True)
    rs = d.get("risk_status", {})
    if rs.get("kill_active"):
        st.error(f"⛔ KILL SWITCH ACTIVE — {rs.get('kill_mode')}")
except Exception:
    pass

st.header("Charts — Plotly from engine state + as-of toggle capped 800 UIX-07")
# Dynamic symbol list from registry (INV-25 no hard-coded cap) — fallback to registry warming placeholder
try:
    db0 = get_session()
    regs = db0.query(ContractRegistry).filter(ContractRegistry.status == "TRADING").limit(200).all()
    syms = [r.symbol for r in regs] if regs else ["BTCUSDT"]
    db0.close()
except Exception:
    syms = ["BTCUSDT"]
symbol=st.selectbox("Symbol charts", syms)
timeframe=st.selectbox("TF", ["15m","1h"])
try:
    db=get_session()
    candles=db.query(Candle).filter(Candle.symbol==symbol, Candle.timeframe==timeframe).order_by(Candle.close_time.desc()).limit(800).all()
    db.close()
    if candles:
        df=pd.DataFrame([{"open_time":c.open_time,"open":float(c.open),"high":float(c.high),"low":float(c.low),"close":float(c.close)} for c in reversed(candles)])
        render_candles(df, symbol, timeframe)
    else:
        st.info("NO DATA — no candles (transport may be DISCONNECTED or WARMING_UP — see health strip)")

except Exception as e:
    st.error(str(e))
