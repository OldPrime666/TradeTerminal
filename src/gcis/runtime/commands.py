"""
Commands P09 OPS-11 — idempotent command handling via supervisors handle_command.

Thin wrapper for CLI / UI to submit commands (KILL_SWITCH, etc.)
"""
from gcis.runtime.supervisor import get_supervisor

def submit_command(idempotency_key: str, cmd_type: str, payload: dict):
    sup = get_supervisor()
    return sup.handle_command(idempotency_key, cmd_type, payload)

def submit_kill_switch(idempotency_key: str, mode: str = "BLOCK_NEW_TRADES", reason: str = "manual"):
    return submit_command(idempotency_key, "KILL_SWITCH", {"mode": mode, "reason": reason})
