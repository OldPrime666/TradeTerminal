"""Risk domain ports — abstractions for kill switch persistence.

Domain must not import sqlalchemy or persistence models.
Persistence adapter implements this protocol.
"""
from typing import Protocol, Any

class KillSwitchStore(Protocol):
    """Abstract store for kill switch state. Implemented in persistence layer."""

    def is_active(self) -> bool: ...

    def activate(self, reason: str, mode: str = "BLOCK_NEW_TRADES") -> Any: ...

    def deactivate(self) -> Any: ...

    # For backward compat with Session-like stores, we also support query interface
    # but the protocol itself is minimal.
