from __future__ import annotations

import asyncio
import json
import threading
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[str]]] = {}
        self._lock = threading.Lock()

    def subscribe(self, session_id: str) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1000)
        with self._lock:
            if session_id not in self._subscribers:
                self._subscribers[session_id] = []
            self._subscribers[session_id].append(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue[str]) -> None:
        with self._lock:
            if session_id in self._subscribers:
                try:
                    self._subscribers[session_id].remove(queue)
                except ValueError:
                    pass
                if not self._subscribers[session_id]:
                    del self._subscribers[session_id]

    def emit(self, session_id: str, event_type: str, data: dict[str, Any]) -> None:
        payload = json.dumps({"type": event_type, "data": data}, ensure_ascii=False)
        with self._lock:
            queues = list(self._subscribers.get(session_id, []))
        dead: list[asyncio.Queue[str]] = []
        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(q)
        if dead:
            with self._lock:
                for q in dead:
                    try:
                        self._subscribers[session_id].remove(q)
                    except (ValueError, KeyError):
                        pass
                if session_id in self._subscribers and not self._subscribers[session_id]:
                    del self._subscribers[session_id]


event_bus = EventBus()
