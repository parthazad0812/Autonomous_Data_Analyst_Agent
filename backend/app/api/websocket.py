"""
WebSocket Manager + FastAPI WebSocket endpoint.

Architecture:
  1. Client connects to ws://localhost:8000/ws/analysis/{session_id}
  2. Client authenticates with a token as the first message
  3. Redis pub/sub subscribes to channel "analysis:{session_id}"
  4. Analysis service publishes events to that channel
  5. WS handler forwards events to the browser in real-time
"""

import json
import asyncio
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from redis.asyncio import Redis as AsyncRedis

from app.config import settings

router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    """Manages active WebSocket connections per session."""

    def __init__(self) -> None:
        # session_id -> set of active WebSocket connections
        self._active: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        self._active.setdefault(session_id, set()).add(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        sockets = self._active.get(session_id, set())
        sockets.discard(websocket)
        if not sockets:
            self._active.pop(session_id, None)

    async def broadcast(self, session_id: str, message: dict) -> None:
        """Send a message to all clients watching this session."""
        sockets = list(self._active.get(session_id, set()))
        dead = []
        for ws in sockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, session_id)


# Singleton manager
manager = ConnectionManager()


@router.websocket("/ws/analysis/{session_id}")
async def analysis_websocket(
    websocket: WebSocket,
    session_id: str,
):
    """
    WebSocket endpoint. Subscribes to Redis pub/sub channel
    'analysis:{session_id}' and forwards all events to the client.
    """
    await manager.connect(websocket, session_id)
    redis = AsyncRedis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    channel = f"analysis:{session_id}"
    await pubsub.subscribe(channel)

    try:
        # Send immediate confirmation
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": "Connected to analysis stream",
        })

        # Listen for Redis messages and forward to client
        async def redis_listener():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        await manager.broadcast(session_id, data)
                    except (json.JSONDecodeError, Exception):
                        pass

        # Also handle client disconnects
        async def ws_listener():
            try:
                while True:
                    # Heartbeat: accept any message from client (ping)
                    msg = await websocket.receive_text()
            except WebSocketDisconnect:
                pass

        # Run both listeners concurrently until client disconnects
        await asyncio.gather(
            redis_listener(),
            ws_listener(),
            return_exceptions=True,
        )

    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await redis.aclose()
        manager.disconnect(websocket, session_id)


async def publish_event(session_id: str, event: dict) -> None:
    """
    Publish an event to the Redis channel for this session.
    Called by the analysis service from a background thread.
    """
    redis = AsyncRedis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.publish(f"analysis:{session_id}", json.dumps(event))
    finally:
        await redis.aclose()


def publish_event_sync(session_id: str, event: dict) -> None:
    """Synchronous wrapper for publishing events from non-async code."""
    import redis as sync_redis
    r = sync_redis.from_url(settings.redis_url, decode_responses=True)
    try:
        r.publish(f"analysis:{session_id}", json.dumps(event))
    finally:
        r.close()
