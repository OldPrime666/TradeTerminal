"""Webhook notifier — P22 last feature: free webhook without secrets (failover stub)."""
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

def send_webhook(url: str, payload: Dict[str,Any], timeout: int = 5) -> Dict[str,Any]:
    """
    Sends JSON payload to webhook URL. No API keys required for free endpoints (e.g., webhook.site).
    Returns dict with ok/status. Does not raise — failover path returns ok=False.
    """
    if not url or not url.startswith("http"):
        return {"ok": False, "reason": "invalid_url", "url": url}
    if not payload:
        return {"ok": False, "reason": "empty_payload"}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")[:500]
            return {"ok": resp.status < 400, "status": resp.status, "body": body}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "reason": "http_error", "body": str(e)[:300]}
    except Exception as e:
        return {"ok": False, "reason": "network_error", "error": str(e)[:300]}

def format_alert_payload(symbol: str, signal: str, price: float) -> Dict[str,Any]:
    """Formats standard alert payload — no secrets."""
    return {"symbol": symbol, "signal": signal, "price": price, "source": "GCIS-P22", "ts": __import__("datetime").datetime.utcnow().isoformat()+"Z"}

def healthcheck_webhook(url: str = "") -> Dict[str,Any]:
    """
    Failover stub: if no URL, returns healthcheck ok with note failover.
    Used to satisfy CAP free fallback chain.
    """
    if not url:
        return {"ok": True, "mode": "stub", "note": "no webhook configured — stub ok (free fallback chain)"}
    return send_webhook(url, {"healthcheck": True})
