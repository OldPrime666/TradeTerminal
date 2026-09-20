import streamlit as st
from gcis.app.readmodels.overview import get_strongest, get_top_unvalidated
st.header("Overview — STRONGEST SIGNAL")
strong=get_strongest()
if strong:
    st.success(f"STRONGEST: {strong['symbol']} score {strong['score']} EV_lcb N/A")
else:
    st.warning("STRONGEST SIGNAL: NONE — NO QUALIFIED SETUP")
    st.info("TOP UNVALIDATED CANDIDATE — ranked by setup score only, not executable")
    for c in get_top_unvalidated():
        st.write(c)
