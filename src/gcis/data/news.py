"""
DAT-13 news veto / blackout — macro calendar.
Config news.macro_blackout_minutes before 30 after 30, min_impact_for_veto high, time_safety available_at = max(published_at, detected_at)
Initial state per AS-07: NONE => NEWS UNAVAILABLE, no impact on non-news strategies.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class NewsEvent:
    published_at: datetime
    detected_at: datetime
    impact: str  # low/medium/high/critical
    currency: str
    title: str
    source: str = "macro_calendar"

    @property
    def available_at(self) -> datetime:
        # time_safety: max(published, detected)
        pub = self.published_at
        det = self.detected_at
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        if det.tzinfo is None:
            det = det.replace(tzinfo=timezone.utc)
        return pub if pub >= det else det

    def blackout_window(self, before_min: int =30, after_min: int=30):
        start = self.available_at - timedelta(minutes=before_min)
        end = self.available_at + timedelta(minutes=after_min)
        return start, end

def is_in_blackout(signal_time: datetime, event: NewsEvent, before_min: int=30, after_min: int=30) -> bool:
    if signal_time.tzinfo is None:
        signal_time = signal_time.replace(tzinfo=timezone.utc)
    start, end = event.blackout_window(before_min, after_min)
    return start <= signal_time <= end

def veto_signal(
    signal_time: datetime,
    news_events: List[NewsEvent],
    before_min: int =30,
    after_min: int=30,
    min_impact_for_veto: str ="high",
) -> Dict[str,Any]:
    """
    Returns veto decision: blocked True/False, reason, blocking_event.
    Impact ordering: low < medium < high < critical
    """
    order = {"low":1,"medium":2,"high":3,"critical":4}
    min_level = order.get(min_impact_for_veto, 3)
    # NEWS UNAVAILABLE case: empty list => no veto
    if not news_events:
        return {"blocked": False, "reason": None, "blocking_event": None, "note": "DAT-13 NEWS_UNAVAILABLE: no veto"}
    for ev in news_events:
        lvl = order.get(ev.impact, 0)
        if lvl < min_level:
            continue
        if is_in_blackout(signal_time, ev, before_min, after_min):
            return {"blocked": True, "reason": f"MACRO_BLACKOUT {ev.impact} {ev.currency} {ev.title}", "blocking_event": ev, "available_at": ev.available_at, "note": "DAT-13 macro blackout veto"}
    return {"blocked": False, "reason": None, "blocking_event": None, "note": "no blackout overlap"}

def fetch_macro_calendar_stub() -> List[NewsEvent]:
    """Per AS-07 initial NONE — returns empty list for honest NEWS_UNAVAILABLE."""
    return []

def check_news_veto(signal_time: datetime, config: dict | None =None, events: List[NewsEvent] | None =None) -> Dict[str,Any]:
    """Wrapper reading config."""
    if config:
        news_cfg = config.get("news",{})
        before = news_cfg.get("macro_blackout_minutes",{}).get("before",30)
        after = news_cfg.get("macro_blackout_minutes",{}).get("after",30)
        min_impact = news_cfg.get("min_impact_for_veto","high")
    else:
        before, after, min_impact = 30,30,"high"
    evs = events if events is not None else fetch_macro_calendar_stub()
    return veto_signal(signal_time, evs, before, after, min_impact)
