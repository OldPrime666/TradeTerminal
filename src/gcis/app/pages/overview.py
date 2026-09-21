import streamlit as st
from gcis.app.readmodels.overview import get_strongest, get_top_unvalidated
from gcis.runtime.health import compute_health

# Truthful health strip — WorkerState/ProviderStatus + risk_status (WEBSOCKET/DEGRADED/DISCONNECTED)
try:
    h = compute_health()
    d = h.get("details", {})
    tr = d.get("transport_status", "NO DATA")
    rs = d.get("risk_status", {})
    badge = "badge-healthy" if tr == "WEBSOCKET" else "badge-degraded" if tr == "DEGRADED" else "badge-no-data"
    kill_txt = "⛔ KILL ACTIVE" if rs.get("kill_active") else f"Risk:{rs.get('risk_lock','UNKNOWN')}"
    st.markdown(f"<div class='badge {badge}'>Transport: {tr}</div> <span class='small'>{kill_txt} · Data:{h.get('verdict')} · freshness:{d.get('candle_freshness')}</span>", unsafe_allow_html=True)
    if rs.get("kill_active"):
        st.error(f"⛔ KILL SWITCH ACTIVE — {rs.get('kill_mode')} — {rs.get('kill_reason')}")
    with st.expander("Health truth (WorkerState / ProviderStatus / Risk)", expanded=False):
        st.json(h)
except Exception as e:
    st.caption(f"Health unavailable: {e}")

st.header("Overview — STRONGEST SIGNAL")
strong=get_strongest()
if strong:
    st.success(f"STRONGEST: {strong['symbol']} score {strong['score']} EV_lcb N/A")
else:
    st.warning("STRONGEST SIGNAL: NONE — NO QUALIFIED SETUP")
    st.info("TOP UNVALIDATED CANDIDATE — ranked by setup score only, not executable")
    for c in get_top_unvalidated():
        st.write(c)
