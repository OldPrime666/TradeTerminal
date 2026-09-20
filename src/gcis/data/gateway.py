import time
from collections import deque
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last = time.monotonic()
    def consume(self, tokens=1):
        now = time.monotonic()
        elapsed = now - self.last
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last = now
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

class ProviderGateway:
    """
    Single gateway per provider owning token buckets, retry, counters.
    Uses <=50% of published budget (config transport.rest_rate_budget_fraction)
    """
    def __init__(self, name: str, requests_per_min: int = 1200, budget_fraction: float = 0.5):
        self.name = name
        # 1200 req/min ≈ 20/sec; we use 50% =>10/sec
        budget = max(1, int(requests_per_min * budget_fraction))
        self.bucket = TokenBucket(rate=budget/60, capacity=budget)
        self.requests = 0
        self.throttled = 0
        self.errors = 0
        self.last_success = None
        self.last_failure = None

    def allow(self) -> bool:
        ok = self.bucket.consume(1)
        if not ok:
            self.throttled += 1
        return ok

    @retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=10))
    def call(self, func, *args, **kwargs):
        if not self.allow():
            # wait a bit
            time.sleep(0.2)
            if not self.allow():
                raise RuntimeError(f"Gateway {self.name} throttled")
        try:
            res = func(*args, **kwargs)
            self.requests += 1
            self.last_success = time.time()
            return res
        except Exception as e:
            self.errors += 1
            self.last_failure = time.time()
            raise

    def status(self):
        return {"requests": self.requests, "throttled": self.throttled, "errors": self.errors, "last_success": self.last_success, "last_failure": self.last_failure}
