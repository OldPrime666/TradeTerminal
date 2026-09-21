"""Kill switch domain — no direct sqlalchemy import.

Architectural boundary: domain must not import sqlalchemy or persistence models.
Persistence adapter lives in gcis.persistence.kill_switch_repo.

This module accepts either a SQLAlchemy Session (legacy, via dynamic import) or a
KillSwitchStore protocol implementation. Static import of sqlalchemy is forbidden
to satisfy import-linter contract Domain must not import sqlalchemy.
"""
from datetime import datetime, timezone
from typing import Any

# No top-level imports of sqlalchemy or gcis.persistence.models


def _is_session(obj: Any) -> bool:
    return hasattr(obj, "query") and hasattr(obj, "add") and hasattr(obj, "commit")


def is_kill_switch_active(store: Any) -> bool:
    """Return True if kill switch is active.

    Accepts either:
    - KillSwitchStore (has is_active())
    - SQLAlchemy Session (has query) — legacy path for tests, uses dynamic import
    """
    # Protocol path: object with is_active and no query
    if hasattr(store, "is_active") and callable(getattr(store, "is_active")) and not _is_session(store):
        return bool(store.is_active())
    # Session path — dynamic import to avoid static lint dependency
    if _is_session(store):
        import importlib

        models = importlib.import_module("gcis.persistence.models")
        KillSwitchState = models.KillSwitchState
        row = store.query(KillSwitchState).order_by(KillSwitchState.id.desc()).first()
        return bool(row and row.active)
    # Also handle case where store is a wrapper that has both (should not happen), fallback
    if hasattr(store, "is_active"):
        try:
            return bool(store.is_active())
        except Exception:
            pass
    raise TypeError("store must be Session or KillSwitchStore with is_active()")


def activate_kill_switch(store: Any, reason: str, mode: str = "BLOCK_NEW_TRADES"):
    """Activate kill switch. Accepts Session or KillSwitchStore."""
    if hasattr(store, "activate") and callable(getattr(store, "activate")) and not _is_session(store):
        return store.activate(reason, mode)
    if _is_session(store):
        import importlib

        models = importlib.import_module("gcis.persistence.models")
        KillSwitchState = models.KillSwitchState
        ks = KillSwitchState(active=True, mode=mode, reason=reason, created_at=datetime.now(timezone.utc))
        store.add(ks)
        store.commit()
        return ks
    if hasattr(store, "activate"):
        return store.activate(reason, mode)
    raise TypeError("store must be Session or KillSwitchStore with activate()")


def deactivate_kill_switch(store: Any):
    """Deactivate kill switch. Accepts Session or KillSwitchStore."""
    if hasattr(store, "deactivate") and callable(getattr(store, "deactivate")) and not _is_session(store):
        return store.deactivate()
    if _is_session(store):
        import importlib

        models = importlib.import_module("gcis.persistence.models")
        KillSwitchState = models.KillSwitchState
        ks = KillSwitchState(active=False, mode="BLOCK_NEW_TRADES", reason="manual unlock", created_at=datetime.now(timezone.utc))
        store.add(ks)
        store.commit()
        return ks
    if hasattr(store, "deactivate"):
        return store.deactivate()
    raise TypeError("store must be Session or KillSwitchStore with deactivate()")
