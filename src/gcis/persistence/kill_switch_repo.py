"""Persistence adapter for kill switch — implements risk.ports.KillSwitchStore.

This is the ONLY place where sqlalchemy and models are imported for kill switch.
Domain (gcis.risk) must not import sqlalchemy directly.
"""
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from gcis.persistence.models import KillSwitchState

class SqlAlchemyKillSwitchStore:
    """Adapter that implements KillSwitchStore using a SQLAlchemy Session."""

    def __init__(self, db: Session):
        self.db = db

    def is_active(self) -> bool:
        row = self.db.query(KillSwitchState).order_by(KillSwitchState.id.desc()).first()
        return bool(row and row.active)

    def activate(self, reason: str, mode: str = "BLOCK_NEW_TRADES"):
        ks = KillSwitchState(active=True, mode=mode, reason=reason, created_at=datetime.now(timezone.utc))
        self.db.add(ks)
        self.db.commit()
        return ks

    def deactivate(self):
        ks = KillSwitchState(active=False, mode="BLOCK_NEW_TRADES", reason="manual unlock", created_at=datetime.now(timezone.utc))
        self.db.add(ks)
        self.db.commit()
        return ks

# Backward-compat helpers for callers that still pass Session directly
def is_active_via_session(db: Session) -> bool:
    return SqlAlchemyKillSwitchStore(db).is_active()

def activate_via_session(db: Session, reason: str, mode: str = "BLOCK_NEW_TRADES"):
    return SqlAlchemyKillSwitchStore(db).activate(reason, mode)

def deactivate_via_session(db: Session):
    return SqlAlchemyKillSwitchStore(db).deactivate()
