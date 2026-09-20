import streamlit as st
from gcis.persistence.db import get_session
from gcis.persistence.models import PaperAccount, DailyRiskState
st.header("Risk Center UIX-08")
try:
    db=get_session()
    acct=db.query(PaperAccount).first()
    dr=db.query(DailyRiskState).order_by(DailyRiskState.risk_day.desc()).first()
    db.close()
    if acct:
        st.metric("Equity", float(acct.equity))
    if dr:
        st.metric("Risk lock", dr.risk_lock)
    else:
        st.info("Risk state warming up")
except Exception as e:
    st.error(str(e))
