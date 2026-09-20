from datetime import datetime, timezone
import time

class Clock:
    def now_us(self) -> int:
        raise NotImplementedError
    def now(self) -> datetime:
        raise NotImplementedError

class LiveClock(Clock):
    def now_us(self) -> int:
        return int(time.time() * 1_000_000)
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

class ReplayClock(Clock):
    def __init__(self, start_us: int):
        self._us = start_us
    def set(self, us: int):
        self._us = us
    def advance(self, delta_us: int):
        self._us += delta_us
    def now_us(self) -> int:
        return self._us
    def now(self) -> datetime:
        return datetime.fromtimestamp(self._us / 1_000_000, tz=timezone.utc)
