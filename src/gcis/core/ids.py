import ulid

def new_id(prefix: str = "") -> str:
    u = ulid.new()
    return f"{prefix}{str(u)}" if prefix else str(u)

def new_signal_id() -> str:
    return new_id("sig_")

def new_order_id() -> str:
    return new_id("ord_")

def new_intent_id() -> str:
    return new_id("int_")

def new_position_id() -> str:
    return new_id("pos_")
