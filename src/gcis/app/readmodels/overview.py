"""Readmodel overview UIX-05 — STRONGEST by EV_lcb else NONE+TOP UNVALIDATED."""
from gcis.persistence.db import get_session
from gcis.persistence.models import Signal

def get_strongest():
    db=get_session()
    try:
        # EV_lcb ranking would be here; for P11 we use setup_score as proxy
        q=db.query(Signal).filter(Signal.state=="QUALIFIED").order_by(Signal.setup_score.desc()).first()
        if q:
            return {"symbol":q.symbol,"direction":q.direction,"score":q.setup_score,"ev_lcb":None,"status":"UNVALIDATED"}
        return None
    finally:
        db.close()

def get_top_unvalidated(limit=5):
    db=get_session()
    try:
        rows=db.query(Signal).order_by(Signal.setup_score.desc()).limit(limit).all()
        return [{"symbol":r.symbol,"score":r.setup_score} for r in rows]
    finally:
        db.close()
