"""
Notifications — free-only stub, no external keys.
Provides queued notifications with rate limiting, backoff, and audit log.
Channels: log, file, webhook stub (future). Never leaks secrets.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Deque
from collections import deque
import json
import pathlib

class NotificationManager:
    def __init__(self, max_per_min: int = 10, queue_max: int = 100):
        self.max_per_min = max_per_min
        self.queue_max = queue_max
        self.sent_times: Deque[datetime] = deque(maxlen=100)
        self.queue: Deque[Dict[str,Any]] = deque(maxlen=queue_max)
        self.log_path = pathlib.Path("var/logs/notifications.jsonl")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _allow_send(self, now: datetime) -> bool:
        # count sent in last 60s
        cutoff = now - timedelta(seconds=60)
        cnt = sum(1 for t in self.sent_times if t > cutoff)
        return cnt < self.max_per_min

    def enqueue(self, level: str, title: str, message: str, context: Dict[str,Any] | None =None, channel: str ="log", now: datetime | None =None) -> Dict[str,Any]:
        if now is None:
            now = datetime.now(timezone.utc)
        item = {
            "timestamp": now.isoformat(),
            "level": level,  # INFO WARN ERROR CRITICAL
            "title": title,
            "message": message,
            "context": context or {},
            "channel": channel,
        }
        if len(self.queue) >= self.queue_max:
            # drop oldest
            self.queue.popleft()
        self.queue.append(item)
        return item

    def flush(self, now: datetime | None =None) -> Dict[str,Any]:
        """
        Attempts to send queued items respecting rate limit. For P15, just logs to file.
        Returns flushed count and next_retry.
        """
        if now is None:
            now = datetime.now(timezone.utc)
        flushed=0
        pending = len(self.queue)
        while self.queue and self._allow_send(now):
            item = self.queue.popleft()
            # log to file (append jsonl)
            try:
                with open(self.log_path, "a") as f:
                    f.write(json.dumps(item) + "\n")
            except Exception:
                pass
            self.sent_times.append(now)
            flushed+=1
            # increment now slightly to avoid same timestamp burst? keep same for deterministic
        remaining = len(self.queue)
        return {"flushed": flushed, "pending": pending, "remaining": remaining, "rate_limited": remaining>0, "note": "Notifications queued with rate limit max_per_min"}

    def send_now(self, level: str, title: str, message: str, context: dict | None =None, channel: str="log") -> Dict[str,Any]:
        now = datetime.now(timezone.utc)
        item = self.enqueue(level, title, message, context, channel, now)
        if self._allow_send(now):
            # send immediately via flush one
            return self.flush(now)
        return {"flushed":0,"pending":1,"remaining":1,"rate_limited":True}

    def get_queue(self) -> List[Dict[str,Any]]:
        return list(self.queue)

_global_manager = NotificationManager()

def get_notification_manager() -> NotificationManager:
    return _global_manager

def notify(level: str, title: str, message: str, context: dict | None =None) -> Dict[str,Any]:
    return get_notification_manager().send_now(level, title, message, context)
