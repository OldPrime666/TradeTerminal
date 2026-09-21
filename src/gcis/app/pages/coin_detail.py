import streamlit as st
from gcis.persistence.db import get_session
from gcis.persistence.models import Candle, LatestQuote, ContractRegistry
from gcis.runtime.health import compute_health
import pandas as pd

try:
    h = compute_health()
    d = h.get("details", {})
    tr = d.get("transport_status", "NO DATA")
    badge = "badge-healthy" if tr == "WEBSOCKET" else "badge-degraded" if tr == "DEGRADED" else "badge-no-data"
    st.markdown(f"<div class='badge {badge}'>Transport: {tr}</div> <span class='small'>Data:{h.get('verdict')} · {d.get('candle_freshness')}</span>", unsafe_allow_html=True)
    rs = d.get("risk_status", {})
    if rs.get("kill_active"):
        st.error(f"⛔ KILL SWITCH ACTIVE — new entries BLOCKED ({rs.get('kill_mode')})")
    elif rs.get("risk_lock") == "LOCKED":
        st.warning(f"🔒 DAILY RISK LOCK — {rs.get('trades_today')} trades today (00:00 UTC reset)")
except Exception:
    pass

st.header("Coin Detail — Regime/ICT/Orderbook Freshness UIX-06")
# Dynamic symbols from registry
try:
    db0 = get_session()
    regs = db0.query(ContractRegistry).filter(ContractRegistry.status == "TRADING").limit(200).all()
    syms = [r.symbol for r in regs] if regs else ["BTCUSDT","ETHUSDT"]
    db0.close()
except Exception:
    syms = ["BTCUSDT","ETHUSDT"]
symbol=st.selectbox("Symbol", syms)
try:
    db=get_session()
    q=db.query(LatestQuote).filter(LatestQuote.symbol==symbol).first()
    if q:
        st.metric("Price", float(q.price))
        st.caption(f"Source:{q.source} · venue:{q.venue} · Freshness: {( __import__('datetime').datetime.now(__import__('datetime').timezone.utc)-q.updated_at).total_seconds():.0f}s · transport:{tr if 'tr' in locals() else 'UNKNOWN'}")
        # live quote age truth: <5s HEALTHY, else STALE → DOM disabled
        age = (__import__('datetime').datetime.now(__import__('datetime').timezone.utc)-q.updated_at).total_seconds()
        if age > 30:
            st.warning(f"STALE quote — {age:.0f}s ago — market strategies that need DOM/L2 are BLOCKED (health truth)")
    else:
        st.warning("NO DATA — no quote (transport DISCONNECTED or WARMING_UP — see health strip)")

    db.close()
except Exception as e:
    st.error(str(e))
