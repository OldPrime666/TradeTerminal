"""Kill switch domain — depends only on KillSwitchStore protocol, no sqlalchemy."""

from typing import Any
from gcis.risk.ports import KillSwitchStore

def is_kill_switch_active(store: KillSwitchStore) -> bool:
    """Return True if kill switch is active — accepts only KillSwitchStore."""
    return bool(store.is_active())

def activate_kill_switch(store: KillSwitchStore, reason: str, mode: str = "BLOCK_NEW_TRADES"):
    return store.activate(reason, mode)

def deactivate_kill_switch(store: KillSwitchStore):
    return store.deactivate()
