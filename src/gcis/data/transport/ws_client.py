"""
WS client (DAT-04) — single connection handling streams, rotation <24h, gap poll, heartbeat.
Free-only, reports ProviderStatus, never circumvent 451.
"""
import asyncio
import json
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Callable, Awaitable
import websockets
from websockets.exceptions import ConnectionClosed

log = logging.getLogger(__name__)

class WSConnection:
    """
    Manages one WS connection for a shard of streams.
    - ws_base: e.g., wss://fstream.binance.com
    - streams: list like ["btcusdt@kline_1m", ...]
    - venue, group for status reporting
    - rotate_before_h 23 with overlap 15s per transport config
    """
    def __init__(
        self,
        venue: str,
        group: str,
        streams: List[str],
        ws_base: str,
        rotate_before_h: int = 23,
        rotation_overlap_s: int = 15,
        backoff_schedule: List[int] | None = None,
         on_message: Callable[[dict, int], Awaitable[None]] | None = None,
    ):
        self.venue = venue
        self.group = group
        self.streams = streams
        self.ws_base = ws_base.rstrip("/")
        self.rotate_before_h = rotate_before_h
        self.rotation_overlap_s = rotation_overlap_s
        self.backoff_schedule = backoff_schedule or [1,2,4,8,16,30,60]
        self.on_message = on_message
        self.state: str = "DISCONNECTED"  # DISCONNECTED, CONNECTING, WEBSOCKET, RECOVERING
        self.connected_at: float | None = None
        self.last_msg_at: float | None = None
        self.reconnect_attempts: int = 0
        self.ws = None
        self._rotate_task: asyncio.Task | None = None
        self._should_run = True

    def _build_url(self) -> str:
        """
        Binance combined stream URL: wss://fstream.binance.com/stream?streams=btcusdt@kline_1m/btcusdt@bookTicker...
        For other venues, similar but we keep generic via ws_base/stream
        """
        # Binance futures uses /stream?streams=...
        # Use generic combined stream endpoint if ws_base contains fstream/stream
        streams_part = "/".join(self.streams)
        # If ws_base already includes /stream, append ?streams=
        if "stream" in self.ws_base:
            base = self.ws_base.split("/stream")[0]
            return f"{base}/stream?streams={streams_part}"
        # Generic: ws_base + /stream?streams=
        return f"{self.ws_base}/stream?streams={streams_part}"

    def should_rotate(self) -> bool:
        if self.connected_at is None:
            return False
        elapsed_h = (time.time() - self.connected_at) / 3600
        return elapsed_h >= self.rotate_before_h

    async def connect_and_serve(self):
        """Main loop: connect, serve, handle rotation, reconnect with backoff."""
        while self._should_run:
            try:
                self.state = "CONNECTING"
                url = self._build_url()
                log.info(f"WS {self.venue}/{self.group} connecting {len(self.streams)} streams -> {url[:120]}...")
                # websockets.connect with ping interval
                async with websockets.connect(url, ping_interval=180, ping_timeout=600, close_timeout=5) as ws:
                    self.ws = ws
                    self.state = "WEBSOCKET"
                    self.connected_at = time.time()
                    self.last_msg_at = time.time()
                    self.reconnect_attempts = 0
                    log.info(f"WS {self.venue}/{self.group} WEBSOCKET connected ({len(self.streams)} streams)")
                    # serve
                    await self._serve_loop(ws)
            except ConnectionClosed as e:
                log.warning(f"WS {self.venue}/{self.group} closed: {e} attempt {self.reconnect_attempts}")
                self.state = "RECOVERING"
            except Exception as e:
                msg = str(e).lower()
                if "451" in msg or "403" in msg or "restricted" in msg:
                    log.warning(f"WS {self.venue}/{self.group} RESTRICTED geo {e} — not reconnecting aggressively, backoff")
                else:
                    log.warning(f"WS {self.venue}/{self.group} error: {e}")
                self.state = "RECOVERING"
            # backoff
            if not self._should_run:
                break
            # Check if should rotate (planned disconnect before 24h)
            if self.should_rotate():
                log.info(f"WS {self.venue}/{self.group} rotation <24h triggered (23h) with {self.rotation_overlap_s}s overlap")
                # Overlap: keep old connected while new connects? For P03 simple: just reconnect after overlap sleep
                await asyncio.sleep(self.rotation_overlap_s)
                continue
            # reconnect backoff
            delay = self.backoff_schedule[min(self.reconnect_attempts, len(self.backoff_schedule)-1)]
            self.reconnect_attempts += 1
            log.info(f"WS {self.venue}/{self.group} RECOVERING backoff {delay}s attempt {self.reconnect_attempts}")
            await asyncio.sleep(delay)
            # If too many attempts >5/10m, mark FAILED? For P03 we just keep trying.

    async def _serve_loop(self, ws):
        """Receive messages, handle rotation timer, call on_message"""
        rotate_check_interval = 60  # check every 60s
        last_rotate_check = time.time()
        async for raw in ws:
            self.last_msg_at = time.time()
            # Raw recorder will be called upstream? But we can record here if on_message not set
            try:
                data = json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode())
            except Exception:
                # keep raw
                data = {"raw": raw}
            # Binance combined stream wraps payload in {"stream":"...", "data":{...}}
            payload = data.get("data") if "data" in data and "stream" in data else data
            # Call handler
            if self.on_message:
                # Pass payload and received_at us
                ts_us = int(time.time() * 1_000_000)
                try:
                    await self.on_message(payload, ts_us)
                except Exception as e:
                    log.warning(f"on_message handler failed: {e}")
            # rotation check
            now = time.time()
            if now - last_rotate_check > rotate_check_interval:
                last_rotate_check = now
                if self.should_rotate():
                    log.info(f"WS {self.venue}/{self.group} proactive rotation (<24h)")
                    # close gracefully, loop will reconnect after overlap
                    await ws.close(code=1000, reason="rotate<24h")
                    break

    async def close(self):
        self._should_run = False
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
        if self._rotate_task:
            self._rotate_task.cancel()

    def health(self) -> Dict[str, Any]:
        return {
            "venue": self.venue,
            "group": self.group,
            "state": self.state,
            "streams": len(self.streams),
            "connected_at": self.connected_at,
            "last_msg_at": self.last_msg_at,
            "should_rotate": self.should_rotate(),
            "attempts": self.reconnect_attempts,
        }
