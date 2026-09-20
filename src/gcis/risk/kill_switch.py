from datetime import datetime, timezone
from sqlalchemy.orm import Session
from gcis.persistence.models import KillSwitchState

def is_kill_switch_active(db: Session) -> bool:
    row = db.query(KillSwitchState).order_by(KillSwitchState.id.desc()).first()
    return bool(row and row.active)

def activate_kill_switch(db: Session, reason: str, mode: str = "BLOCK_NEW_TRADES"):
    ks = KillSwitchState(active=True, mode=mode, reason=reason, created_at=datetime.now(timezone.utc))
    db.add(ks)
    db.commit()
    return ks

def deactivate_kill_switch(db: Session):
    ks = KillSwitchState(active=False, mode="BLOCK_NEW_TRADES", reason="manual unlock", created_at=datetime.now(timezone.utc))
    db.add(ks)
    db.commit()
    return ks
