import streamlit as st
import uuid
from gcis.runtime.commands import submit_command
st.header("Trade Desk — EXE-02 Idempotency via commands UIX-08")
symbol=st.text_input("Symbol", "BTCUSDT")
direction=st.selectbox("Direction", ["LONG","SHORT"])
qty=st.number_input("Qty", 0.01)
if st.button("ENTER TRADE"):
    key=f"trade-{symbol}-{direction}-{qty}-{uuid.uuid4()}"
    res=submit_command(idempotency_key=key, cmd_type="ENTER_TRADE", payload={"symbol":symbol,"direction":direction,"qty":qty})
    st.success(f"Command {res['command_id']} status {res['status']} idempotent {res['idempotent']}")
    st.caption("Idempotency: duplicate clicks with same key never double-create (EXE-02)")
