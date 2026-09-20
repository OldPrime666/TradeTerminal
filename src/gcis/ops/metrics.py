"""
OPS-09 metrics 1m rollups — ingest, latency, health.
Config performance_budgets: candle_close_to_signal_persisted_s 3, ui_page_render_s 2, ingest_to_persist_p95_ms 250, memory_growth 50, scale bundle_latency_budget 20
Deterministic 1m buckets.
"""
import time
from collections import deque, defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Deque
import statistics

class MetricsRollup:
    def __init__(self):
        self.ingest_to_persist_ms: Deque[float] = deque(maxlen=1000)
        self.candle_to_signal_s: Deque[float] = deque(maxlen=1000)
        self.ui_render_ms: Deque[float] = deque(maxlen=1000)
        self.bundle_latency_s: Deque[float] = deque(maxlen=1000)
        self.memory_samples: Deque[float] = deque(maxlen=1000)
        self.events_1m: Dict[str, int] = defaultdict(int)
        self.last_1m_rollup: datetime | None = None

    def record_ingest_to_persist(self, ms: float):
        self.ingest_to_persist_ms.append(float(ms))
        self.events_1m["ingest"]+=1

    def record_candle_to_signal(self, s: float):
        self.candle_to_signal_s.append(float(s))

    def record_bundle_latency(self, s: float):
        self.bundle_latency_s.append(float(s))

    def budget_status(self) -> Dict[str,Any]:
        """
        Compare p95 vs budget thresholds.
        """
        def p95(vals):
            if not vals:
                return None
            sorted_vals = sorted(vals)
            idx = int(0.95*len(sorted_vals))
            idx = min(idx, len(sorted_vals)-1)
            return sorted_vals[idx]
        ingest_p95 = p95(self.ingest_to_persist_ms)
        bundle_p95 = p95(self.bundle_latency_s)
        candle_p95 = p95(self.candle_to_signal_s)
        # budgets
        ingest_budget_ms = 250
        candle_budget_s = 3
        bundle_budget_s = 20
        return {
            "ingest_to_persist_p95_ms": ingest_p95,
            "ingest_budget_ms": ingest_budget_ms,
            "ingest_ok": ingest_p95 is None or ingest_p95 <= ingest_budget_ms,
            "candle_to_signal_p95_s": candle_p95,
            "candle_budget_s": candle_budget_s,
            "candle_ok": candle_p95 is None or candle_p95 <= candle_budget_s,
            "bundle_latency_p95_s": bundle_p95,
            "bundle_budget_s": bundle_budget_s,
            "bundle_ok": bundle_p95 is None or bundle_p95 <= bundle_budget_s,
            "note": "OPS-09 1m rollups, budgets per config"
        }

    def rollup_1m(self) -> Dict[str,Any]:
        now = datetime.now(timezone.utc)
        status = self.budget_status()
        # reset per-1m counters after rollup
        events = dict(self.events_1m)
        self.events_1m.clear()
        self.last_1m_rollup = now
        return {"timestamp": now.isoformat(), "events_1m": events, "budgets": status}

# singleton
_global_rollup = MetricsRollup()

def get_metrics_rollup() -> MetricsRollup:
    return _global_rollup
