from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from dataclasses import dataclass

SESSIONS = {
    "asia": {"tz": "Asia/Tokyo", "start": "09:00", "end": "15:00"},
    "london": {"tz": "Europe/London", "start": "08:00", "end": "16:30"},
    "new_york": {"tz": "America/New_York", "start": "08:30", "end": "17:00"},
    "london_killzone": {"tz": "Europe/London", "start": "07:00", "end": "10:00"},
    "new_york_killzone": {"tz": "America/New_York", "start": "07:00", "end": "10:00"},
}

def _parse_hhmm(s: str):
    h, m = map(int, s.split(":"))
    return time(h, m)

def is_session_active(session_key: str, dt_utc: datetime) -> bool:
    cfg = SESSIONS[session_key]
    tz = ZoneInfo(cfg["tz"])
    local = dt_utc.astimezone(tz)
    start = _parse_hhmm(cfg["start"])
    end = _parse_hhmm(cfg["end"])
    lt = local.time()
    # handle overnight sessions (not needed for defaults)
    if start <= end:
        return start <= lt <= end
    else:
        return lt >= start or lt <= end

def active_sessions(dt_utc: datetime) -> list[str]:
    return [k for k in SESSIONS if is_session_active(k, dt_utc)]

def utc_now():
    return datetime.now(timezone.utc)
