import streamlit as st
from gcis.persistence.db import get_session
from gcis.persistence.models import PaperAccount, DailyRiskState, KillSwitchState, WorkerState, ProviderStatus
from gcis.runtime.health import compute_health

st.header("Risk Center UIX-08 — truthful WorkerState/ProviderStatus + DailyRisk/KillSwitch")
# Health truth strip
try:
    h = compute_health()
    d = h.get("details", {})
    tr = d.get("transport_status", "NO DATA")
    badge = "badge-healthy" if tr == "WEBSOCKET" else "badge-degraded" if tr == "DEGRADED" else "badge-no-data"
    st.markdown(f"<div class='badge {badge}'>Transport: {tr}</div> <span class='small'>Data:{h.get('verdict')} · freshness:{d.get('candle_freshness')}</span>", unsafe_allow_html=True)
    rs = d.get("risk_status", {})
    st.json({"transport_status": tr, "workers": d.get("workers"), "risk_status": rs, "providers": d.get("providers")})
    if rs.get("kill_active"):
        st.error(f"⛔ KILL SWITCH ACTIVE — {rs.get('kill_mode')} — {rs.get('kill_reason')} — new trades BLOCKED")
    if rs.get("risk_lock") == "LOCKED":
        st.warning(f"🔒 RISK LOCK ACTIVE — LOCKED (trades {rs.get('trades_today')} today) — new entries BLOCKED until 00:00 UTC")
except Exception as e:
    st.caption(f"Health unavailable: {e}")

try:
    db=get_session()
    acct=db.query(PaperAccount).first()
    dr=db.query(DailyRiskState).order_by(DailyRiskState.risk_day.desc()).first()
    ks=db.query(KillSwitchState).order_by(KillSwitchState.id.desc()).first()
    # Also show WorkerState table truth
    workers = db.query(WorkerState).all()
    providers = db.query(ProviderStatus).all()
    db.close()
    col1, col2 = st.columns(2)
    with col1:
        if acct:
            st.metric("Equity", float(acct.equity))
        if dr:
            st.metric("Risk lock", dr.risk_lock)
            st.caption(f"Trades today {dr.trades_today} · PnL {dr.daily_realized_pnl}")
        else:
            st.info("Risk state warming up — daily state not yet initialized (risk truth: UNKNOWN until first Day starts)")
        if ks and ks.active:
            st.error(f"KILL SWITCH ACTIVE — {ks.mode} — {ks.reason}")
        elif ks:
            st.success(f"Kill switch last: inactive (mode {ks.mode})")
        else:
            st.success("Kill switch: not yet set — ACTIVE (no block)")
    with col2:
        st.subheader("Worker truth")
        if workers:
            for w in workers:
                st.write(f"{w.process}: {w.state} pid={w.pid} hb={w.last_heartbeat} lag={w.lag_ms}ms depth={w.queue_depth}")
        else:
            st.info("No WorkerState yet — transport/analyzer not yet heartbeat (NO DATA is honest)")
        st.subheader("Provider truth")
        if providers:
            for p in providers[:10]:
                st.write(f"{p.provider}: {p.status} age={p.data_age_s}s circuit={p.circuit_state}")
        else:
            st.info("No ProviderStatus yet — warming up (invite preflight)")
except Exception as e:
    st.error(str(e))
