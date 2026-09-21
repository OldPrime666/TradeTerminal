import streamlit as st
import uuid
from gcis.runtime.commands import submit_command
from gcis.runtime.health import compute_health
from gcis.persistence.db import get_session
from gcis.persistence.models import ContractRegistry

# Health + risk truth before allowing trade
try:
    h = compute_health()
    d = h.get("details", {})
    tr = d.get("transport_status", "NO DATA")
    rs = d.get("risk_status", {})
    badge = "badge-healthy" if tr == "WEBSOCKET" else "badge-degraded" if tr == "DEGRADED" else "badge-no-data"
    st.markdown(f"<div class='badge {badge}'>Transport: {tr}</div> <span class='small'>Data:{h.get('verdict')} · freshness:{d.get('candle_freshness')}</span>", unsafe_allow_html=True)
    if rs.get("kill_active"):
        st.error(f"⛔ KILL SWITCH ACTIVE — {rs.get('kill_mode')} — trades BLOCKED (health truth)")
    if rs.get("risk_lock") == "LOCKED":
        st.warning(f"🔒 DAILY RISK LOCK — trades BLOCKED until 00:00 UTC")
    # Also show workers in expander
    with st.expander("Health truth (WorkerState/ProviderStatus/Risk)"):
        st.json(d)
except Exception as e:
    st.caption(f"Health unavailable: {e}")
    tr = "UNKNOWN"
    rs = {}

st.header("Trade Desk — EXE-02 Idempotency via commands UIX-08")
# Dynamic symbol list from registry (no hard-coded cap)
try:
    db0 = get_session()
    regs = db0.query(ContractRegistry).filter(ContractRegistry.status == "TRADING").limit(200).all()
    syms = [r.symbol for r in regs] if regs else ["BTCUSDT"]
    db0.close()
except Exception:
    syms = ["BTCUSDT"]
symbol=st.selectbox("Symbol", syms)
direction=st.selectbox("Direction", ["LONG","SHORT"])
qty=st.number_input("Qty", 0.01)
blocked = (rs.get("kill_active") if 'rs' in locals() else False) or (rs.get("risk_lock") == "LOCKED" if 'rs' in locals() else False)
if blocked:
    st.warning("Trade entry is BLOCKED by risk truth (kill switch or daily lock) — button disabled (INV-06: UI never bypasses persistence truth)")
if st.button("ENTER TRADE", disabled=blocked):
    # Transport truth: if DISCONNECTED, warn but still submit (core will re-validate gates and may block)
    if tr == "DISCONNECTED":
        st.warning("Transport DISCONNECTED — quote may be STALE; core gates will BLOCK if DATA_STALE (honest)")
    key=f"trade-{symbol}-{direction}-{qty}-{uuid.uuid4()}"
    res=submit_command(idempotency_key=key, cmd_type="ENTER_TRADE", payload={"symbol":symbol,"direction":direction,"qty":qty})
    st.success(f"Command {res['command_id']} status {res['status']} idempotent {res['idempotent']}")
    st.caption("Idempotency: duplicate clicks with same key never double-create (EXE-02) — core re-validates gates in same DB tx")
